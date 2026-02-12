import usb.core
import usb.util

# Realtek UB500 IDs from your dmesg: 0bda:b771
dev = usb.core.find(idVendor=0x0bda, idProduct=0xb771)

if dev is None:
    print("Device not found. Is it plugged in?")
else:
    print(f"Device found: {usb.util.get_string(dev, dev.iProduct)}")
    for cfg in dev:
        print(f"Configuration {cfg.bConfigurationValue}:")
        print(f"  MaxPower: {cfg.bMaxPower * 2}mA") # Value is in 2mA units