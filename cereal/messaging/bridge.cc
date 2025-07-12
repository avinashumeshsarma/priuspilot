#include <cassert>
#include <iostream>
#include <thread>

#include "cereal/messaging/msgq_to_zmq.h"
#include "cereal/services.h"
#include "common/util.h"

ExitHandler do_exit;

static std::vector<std::string> get_services(const std::string &whitelist_str, bool zmq_to_msgq) {
  std::vector<std::string> service_list;

  // If filter_str is empty, include all services
  if (whitelist_str.empty()) {
    for (const auto& it : services) {
      service_list.push_back(it.second.name);
    }
    return service_list;
  }

  for (const auto& it : services) {
    std::string name = it.second.name;
    bool in_whitelist = whitelist_str.find(name) != std::string::npos;
    if (zmq_to_msgq){
      if (!in_whitelist) continue;
    } else {
      if (in_whitelist) continue;
    }
    service_list.push_back(name);
  }
  return service_list;
}

void msgq_to_zmq(const std::vector<std::string> &endpoints, const std::string &ip) {
  MsgqToZmq bridge;
  bridge.run(endpoints, ip);
}

void zmq_to_msgq(const std::vector<std::string> &endpoints, const std::string &ip) {
  auto poller = std::make_unique<ZMQPoller>();
  auto pub_context = std::make_unique<MSGQContext>();
  auto sub_context = std::make_unique<ZMQContext>();
  std::map<SubSocket *, PubSocket *> sub2pub;

  for (auto endpoint : endpoints) {
    auto pub_sock = new MSGQPubSocket();
    auto sub_sock = new ZMQSubSocket();
    pub_sock->connect(pub_context.get(), endpoint);
    sub_sock->connect(sub_context.get(), endpoint, ip, false);

    poller->registerSocket(sub_sock);
    sub2pub[sub_sock] = pub_sock;
  }

  while (!do_exit) {
    for (auto sub_sock : poller->poll(100)) {
      std::unique_ptr<Message> msg(sub_sock->receive(true));
      if (msg) {
        sub2pub[sub_sock]->sendMessage(msg.get());
      }
    }
  }

  // Clean up allocated sockets
  for (auto &[sub_sock, pub_sock] : sub2pub) {
    delete sub_sock;
    delete pub_sock;
  }
}

int main(int argc, char **argv) {
  bool is_zmq_to_msgq = argc > 2;
  std::string ip = is_zmq_to_msgq ? argv[1] : "127.0.0.1";
  std::string whitelist_str = is_zmq_to_msgq ? std::string(argv[2]) : "";
  std::vector<std::string> endpoints_listen = get_services(whitelist_str, true);
  std::vector<std::string> endpoints_publish = get_services(whitelist_str, false);

  std::cout << "Listening on:" << std::endl;
  for (const auto& s : endpoints_listen) {
    std::cout << s << std::endl;
  }

  std::cout << "--------------------------------" << std::endl;

  std::cout << "Publishing on all the messages except the above ones" << std::endl;

  // for (const auto& s : endpoints_publish) {
  //   std::cout << s << std::endl;
  // }



  if (is_zmq_to_msgq) {
    std::thread zmq_to_msgq_thread(zmq_to_msgq, endpoints_listen, ip);
    std::thread msgq_to_zmq_thread(msgq_to_zmq, endpoints_publish, ip);
    zmq_to_msgq_thread.join();
    msgq_to_zmq_thread.join();
    // std::cout << "Done" << std::endl;
  } else {
    msgq_to_zmq(endpoints_publish, ip);
  }
  return 0;
}
