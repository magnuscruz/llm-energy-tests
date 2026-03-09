# 1. Remove the previous broken installation (if it exists)
sudo systemctl stop ollama
sudo rm -rf /usr/local/bin/ollama
rm -f ollama-linux-amd64
rm -f ollama.tgz


# 2. Use the official installer from Ollama's website to get the latest version
curl -fsSL https://ollama.com/install.sh | sh
/usr/bin/ollama --version


# 3. CRITICAL: Point the service to your LVM (Home) to avoid the /cow error
# We edit the service file To ensure your 7-model benchmark survives reboots and uses your LVM disk.
sudo mkdir -p /home/ubuntu/.ollama/models
sudo chown -R ubuntu:ubuntu /home/ubuntu
sudo chmod -R 755 /home/ubuntu
sudo rm -f /etc/systemd/system/ollama.service
sudo bash -c 'cat <<EOF > /etc/systemd/system/ollama.service
[Unit]
Description=Ollama Service (Aging Test)
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ubuntu
Group=ubuntu
Restart=always
Environment="OLLAMA_MODELS=/home/ubuntu/.ollama/models"
Environment="HOME=/home/ubuntu"

[Install]
WantedBy=multi-user.target
EOF'


# 4. Reload systemd, enable and start the Ollama service
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
# Wait 5 seconds and test the API
sleep 5
curl http://localhost:11434
