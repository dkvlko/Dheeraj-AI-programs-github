#!/bin/bash

# Must run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi
#!/bin/bash


# Get actual user's home (not /root)
USER_HOME=$(eval echo ~${SUDO_USER:-$USER})
PROFILE_DIR="$USER_HOME/netplan-profiles"

TARGET_FILE="/etc/netplan/01-netcfg.yaml"

echo "=============================="
echo " Netplan Profile Switcher"
echo "=============================="
echo "1. Use 192.168.29.25 (Jio)"
echo "2. Use 192.168.0.25 (TP-Link)"
echo "=============================="

read -p "Change Ethernet Cable then Enter your choice (1 or 2): " choice

# Select profile
if [ "$choice" == "1" ]; then
    PROFILE="$PROFILE_DIR/profile-29.yaml"
elif [ "$choice" == "2" ]; then
    PROFILE="$PROFILE_DIR/profile-0.yaml"
else
    echo "Invalid choice"
    exit 1
fi

# Check if profile exists
if [ ! -f "$PROFILE" ]; then
    echo "❌ Profile not found: $PROFILE"
    exit 1
fi

echo "🧹 Removing old netplan configs..."
rm -f /etc/netplan/*.yaml

echo "📄 Applying profile: $PROFILE"
cp "$PROFILE" "$TARGET_FILE"

echo "🔒 Setting correct permissions..."
chmod 600 "$TARGET_FILE"

echo "⚙️ Applying netplan..."
netplan apply

echo ""
echo "✅ Done.Change the Ethernet Cable."
echo "📡 Current IP(s):"
hostname -I
