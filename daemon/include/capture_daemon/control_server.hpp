// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture_daemon/sim_engine.hpp"

#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace capture::daemon {

// Named-pipe control plane: CSP1 framing + capture.v1 protobuf payloads.
class ControlServer {
 public:
  ControlServer(SimEngine& engine, std::string instance_id, std::string pipe_name);
  ~ControlServer();

  ControlServer(const ControlServer&) = delete;
  ControlServer& operator=(const ControlServer&) = delete;

  bool start(std::string& error);
  void stop();

  const std::string& instance_id() const { return instance_id_; }
  const std::string& pipe_name() const { return pipe_name_; }

 private:
  // One thread per connection. The UI, a CLI, and a second operator screen are
  // all expected to be attached at once, and daemon-held alert acknowledgement
  // and GetSessionView only make sense if late joiners can connect immediately.
  struct Client {
    std::thread thread;
    std::shared_ptr<std::atomic<bool>> done;
    // Closed by whoever joins the thread, never by the thread itself, so that
    // stop() can always CancelIoEx a handle that is still valid.
    void* pipe = nullptr;
  };

  void accept_loop();
  bool await_connection(void* pipe_handle);
  void serve_client(void* pipe_handle);
  void reap_finished_clients();

  SimEngine& engine_;
  std::string instance_id_;
  std::string pipe_name_;
  std::atomic<bool> running_{false};
  std::thread accept_thread_;
  std::mutex clients_mu_;
  std::vector<Client> clients_;
};

bool write_instance_file(const std::string& instance_id,
                         const std::string& pipe_name, std::string& error);

}  // namespace capture::daemon
