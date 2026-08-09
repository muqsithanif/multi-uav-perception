// Copyright 2026 multi-uav-perception
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>

#include "multi_uav_interfaces/msg/mission_status.hpp"
#include "rclcpp/rclcpp.hpp"

class MissionMonitor final : public rclcpp::Node
{
public:
  MissionMonitor()
  : Node("mission_monitor")
  {
    const auto qos = rclcpp::QoS(10).reliable().durability_volatile();
    subscription_ = create_subscription<multi_uav_interfaces::msg::MissionStatus>(
      "mission/status", qos,
      std::bind(&MissionMonitor::on_status, this, std::placeholders::_1));
  }

private:
  void on_status(const multi_uav_interfaces::msg::MissionStatus::SharedPtr message)
  {
    ++received_count_;
    if (last_sequence_ && message->source_sequence < *last_sequence_) {
      RCLCPP_WARN(
        get_logger(), "out_of_order_source_sequence previous=%" PRIu64 " current=%" PRIu64,
        *last_sequence_, message->source_sequence);
    }
    last_sequence_ = std::max(last_sequence_.value_or(0), message->source_sequence);

    const auto age = get_clock()->now() - rclcpp::Time(message->header.stamp);
    RCLCPP_INFO(
      get_logger(),
      "mission_status_count=%" PRIu64 " source_sequence=%" PRIu64
      " vehicle_id=%s track_id=%u state=%s age_ms=%.3f",
      received_count_, message->source_sequence, message->vehicle_id.c_str(), message->track_id,
      message->state.c_str(), static_cast<double>(age.nanoseconds()) / 1.0e6);
  }

  rclcpp::Subscription<multi_uav_interfaces::msg::MissionStatus>::SharedPtr subscription_;
  uint64_t received_count_{0};
  std::optional<uint64_t> last_sequence_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<MissionMonitor>());
  rclcpp::shutdown();
  return 0;
}
