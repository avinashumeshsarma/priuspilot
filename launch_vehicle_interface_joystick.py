#!/usr/bin/env python3
import subprocess
import os
import signal
import time
import sys
import glob # Not explicitly used, but generally useful for file operations

# --- Configuration ---
# Get the absolute path to the directory where this script is located.
# This ensures all relative paths for processes are correct.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the processes to launch.
# "cmd" is the command and its arguments as a list.
# "is_python" indicates if it's a Python script that needs a python interpreter.
PROCESS_CONFIG = {
    "messaging bridge": {"cmd": ["./cereal/messaging/bridge","127.0.0.1","carControl"], "is_python": False},
    "panda daemon": {"cmd": ["./selfdrive/pandad/pandad.py"], "is_python": True},
    # "joystickd": {"cmd": ["./tools/joystick/joystickd.py"], "is_python": True},
    # "joystick control": {"cmd": ["./tools/joystick/joystick_control.py"], "is_python": True},
    "car daemon": {"cmd": ["./selfdrive/car/card.py"], "is_python": True},
}

# List of /dev/shm files that openpilot creates and might need cleaning.
DEV_SHM_FILES = [
    "/dev/shm/can",
    "/dev/shm/carControl",
    "/dev/shm/carOutput",
    "/dev/shm/carParams",
    "/dev/shm/liveTracks",
    "/dev/shm/onroadEvents",
    "/dev/shm/pandaStates",
    "/dev/shm/selfdriveState",
    "/dev/shm/sendcan",
]

# Dictionary to store Popen objects of launched processes for tracking.
launched_processes = {}

def cleanup(signum=None, frame=None):
    """
    Cleans up all launched processes and removes /dev/shm files.
    This function is called on script exit or when a SIGINT/SIGTERM is received.
    """
    print("\n[INFO] Initiating cleanup...")

    # 1. Try to gracefully terminate launched processes
    for name, proc in list(launched_processes.items()): # Iterate on a copy as dict might change during termination
        if proc.poll() is None: # If process is still running
            print(f"  Terminating '{name}' (PID: {proc.pid})...")
            proc.terminate() # Send SIGTERM

    # Give processes a moment to terminate gracefully
    time.sleep(1)

    # 2. Forcefully kill any remaining processes by their names (using pkill for robustness)
    # This catches processes that didn't terminate from the SIGTERM or were launched otherwise
    process_names_to_kill = [
        # "joystickd.py",
        # "joystick_control.py",
        "pandad.py",
        "card.py",
        "bridge"
    ]
    for name in process_names_to_kill:
        try:
            # -f flag matches against full command line
            subprocess.run(["pkill", "-f", name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"  Warning: Could not pkill {name}: {e}")

    # 3. Clean up /dev/shm socket files
    for shm_file in DEV_SHM_FILES:
        try:
            # Use sudo because some files might be owned by root from previous runs
            subprocess.run(["sudo", "rm", "-f", shm_file], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"  Warning: Could not remove {shm_file}: {e}")

    time.sleep(0.5) # Give system a moment after cleanup
    print("[INFO] Cleanup complete.")
    if signum is not None:
        sys.exit(0) # Exit cleanly if called by a signal handler

def launch_process(name, cmd_args, is_python_script, venv_python_executable=None):
    """
    Launches a process in the background and checks if it started successfully.
    """
    full_cmd = []
    if is_python_script:
        # Prepend the Python interpreter executable if it's a Python script
        if venv_python_executable:
            full_cmd.append(venv_python_executable)
        else:
            # Fallback to the system's default python3 or the one running this script
            full_cmd.append(sys.executable)
        full_cmd.extend(cmd_args)
    else:
        full_cmd = cmd_args

    try:
        # subprocess.Popen runs the command in the background.
        # stdout/stderr are inherited from the parent process, so output appears in the terminal.
        process = subprocess.Popen(full_cmd, cwd=SCRIPT_DIR)
        launched_processes[name] = process

        # Check if the process exited immediately after starting
        if process.poll() is not None:
            print(f"[ERROR] Failed to start {name}. Process exited prematurely with code {process.returncode}")
            cleanup()
            sys.exit(1)
        print(f"[INFO] '{name}' started successfully (PID: {process.pid}).")
    except FileNotFoundError:
        print(f"[ERROR] Executable not found for {name}: '{full_cmd[0]}'")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred while starting {name}: {e}")
        cleanup()
        sys.exit(1)

def main():
    # --- Setup Signal Handlers ---
    # Register the cleanup function to be called on script termination (Ctrl+C, kill command)
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # --- Initial Configuration ---
    # Change to the script's directory to ensure all relative paths are correct
    os.chdir(SCRIPT_DIR)

    # Determine the Python executable to use for Python-based processes
    venv_python_executable = None
    venv_activate_script = os.path.join(SCRIPT_DIR, ".venv", "bin", "activate")
    if os.path.exists(venv_activate_script):
        # We can't 'source' in Python. Instead, we'll explicitly use the venv's python executable.
        venv_python_executable = os.path.join(SCRIPT_DIR, ".venv", "bin", "python3")
        if not os.path.exists(venv_python_executable):
            print("[WARN] Virtual environment activate script found, but python3 executable not found in .venv/bin. Using system python.")
            venv_python_executable = None
        else:
            print(f"[INFO] Virtual environment detected. Python executable: {venv_python_executable}")
    else:
        print("[WARN] No virtual environment found at .venv. Using system's default python3.")

    # Set PYTHONPATH to the openpilot root directory for correct module imports
    os.environ["PYTHONPATH"] = SCRIPT_DIR
    print(f"[INFO] PYTHONPATH set to: {os.environ['PYTHONPATH']}")

    # --- Cleanup from Previous Runs ---
    # Perform an initial cleanup to remove any leftover /dev/shm files or processes
    # from previous, potentially crashed, runs.
    # cleanup() # Removed initial cleanup per user request to speed up launch

    print("\n[INFO] Starting vehicle interface with joystick control processes...")

    # --- Launch Processes in Order ---
    # 1. Start messaging bridge (essential for inter-process communication)
    launch_process("messaging bridge", PROCESS_CONFIG["messaging bridge"]["cmd"], PROCESS_CONFIG["messaging bridge"]["is_python"])

    # 2. Start panda daemon (handles communication with Panda hardware)
    # Remember to update your Panda firmware if this fails!
    launch_process("panda daemon", PROCESS_CONFIG["panda daemon"]["cmd"], PROCESS_CONFIG["panda daemon"]["is_python"], venv_python_executable)

    # # 3. Start joystick processes (for manual control input)
    # launch_process("joystickd", PROCESS_CONFIG["joystickd"]["cmd"], PROCESS_CONFIG["joystickd"]["is_python"], venv_python_executable)
    # launch_process("joystick control", PROCESS_CONFIG["joystick control"]["cmd"], PROCESS_CONFIG["joystick control"]["is_python"], venv_python_executable)

    # 4. Start car daemon (simulates car interface based on joystick input)
    launch_process("car daemon", PROCESS_CONFIG["car daemon"]["cmd"], PROCESS_CONFIG["car daemon"]["is_python"], venv_python_executable)

    print("\n[INFO] All primary processes launched. Press Ctrl+C to stop.")

    # --- Monitor Processes ---
    # Keep the script running and monitor all launched processes.
    # If any process exits unexpectedly, the script will clean up and exit.
    try:
        while True:
            for name, proc in list(launched_processes.items()):
                if proc.poll() is not None: # Check if the process has terminated
                    print(f"\n[ERROR] Process '{name}' exited unexpectedly with code {proc.returncode}")
                    cleanup() # Trigger cleanup for remaining processes and files
                    sys.exit(1) # Exit the script with an error code
            time.sleep(0.1) # Check process status every 100ms
    except KeyboardInterrupt:
        # SIGINT will trigger the cleanup function via the signal handler
        pass
    except Exception as e:
        print(f"\n[ERROR] An unhandled exception occurred in the main loop: {e}")
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()
