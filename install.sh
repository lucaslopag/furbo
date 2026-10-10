#!/bin/bash
# Install script for AceStream TV (Linux)

echo "Installing required dependencies for AceStream TV..."

# Check and install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    if command -v dnf &> /dev/null; then
        sudo dnf -y install dnf-plugins-core
        sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
        sudo dnf -y install docker-ce docker-ce-cli containerd.io
        sudo systemctl start docker
        sudo systemctl enable docker
    elif command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y docker.io
        sudo systemctl start docker
        sudo systemctl enable docker
    else
        echo "Please install Docker manually for your distribution."
        exit 1
    fi
else
    echo "Docker is already installed."
fi

# Add user to docker group to avoid sudo password prompts (optional but recommended)
sudo usermod -aG docker $USER
echo "Added user to the docker group."

# Check and install mpv if not present
if ! command -v mpv &> /dev/null; then
    echo "mpv is not installed. Installing mpv..."
    if command -v dnf &> /dev/null; then
        sudo dnf install -y mpv
    elif command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y mpv
    else
        echo "Please install mpv manually for your distribution."
        exit 1
    fi
else
    echo "mpv is already installed."
fi

echo "Pulling required Docker images in advance (this may take a minute)..."
sudo docker pull jopsis/acestream:latest
sudo docker pull dockage/tor-privoxy:latest

echo "Installation complete!"
echo "Please REBOOT your computer (or log out and back in) for the Docker group changes to take effect."
echo "After rebooting, you can run: ./acestream-tv"
