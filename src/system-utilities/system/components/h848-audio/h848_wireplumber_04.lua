-- Redragon H848 / XiiSound-Weltrend 040b:0897

local h848_device_rule = {
  matches = {
    {
      { "device.name", "matches",
        "alsa_card.usb-XiiSound_Technology_Corporation_H848_*" },
    },
  },
  apply_properties = {
    ["device.profile"] = "output:analog-stereo",
    ["api.alsa.soft-mixer"] = true,
    ["api.alsa.ignore-dB"] = true,
    ["api.alsa.split-enable"] = false,
  },
}

local h848_input_rule = {
  matches = {
    {
      { "node.name", "matches",
        "alsa_input.usb-XiiSound_Technology_Corporation_H848_*" },
    },
  },
  apply_properties = {
    ["node.disabled"] = true,
  },
}

table.insert(alsa_monitor.rules, h848_device_rule)
table.insert(alsa_monitor.rules, h848_input_rule)
