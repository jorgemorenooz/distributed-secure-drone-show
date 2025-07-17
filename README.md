# Distributed Secure Drone Show

<p align="center">
  <img src="https://i.pinimg.com/originals/bc/f3/a3/bcf3a371b9303c27752e1109e96a2fe6.gif" alt="Drone GIF">
</p>

# 🛰️ Art with Drones
Art with Drones is a distributed system simulating a coordinated drone light show. Drones move across a grid to form figures in real time, managed by a central engine, with secure communication, resilience to failure, and visual monitoring.

# 📁 Project Structure
```bash
.
├── AD_Engine.py             # Orchestrates drones, assigns figures, handles reconnections
├── AD_Drone.py              # Represents individual autonomous drones
├── AD_Registry.py           # Registers drones and issues secure authentication tokens
├── AD_Display.py            # Real-time visualization using Pygame
├── front.py                 # Flask server hosting the HTML frontend
├── index.html               # Web UI for map and logs
├── certificados/            # TLS certificates (for secure sockets and HTTPS)
├── img/                     # Images used in the display
├── drone_credentials.json   # Stores hashed drone credentials
├── ciudades.json            # City list for weather API
├── AwD_figuras.json         # Scheduled drone formations
└── events.log               # Audit and activity log
```

# ⚙️ Features
- 🔐 Secure Drone Registration & Authentication (TLS + Token + bcrypt)
- 🔄 Resilient Drone Communication (Reconnects, Fallbacks)
- 📡 Kafka-Based Command & Control
- 📺 Real-Time Visualization via Pygame and Web UI
- ☁️ Weather-Driven Show Control
- 🔍 Auditing & Event Logging
- 🌐 REST API and Socket Interfaces

# 🚀 How to Run
## 1. Prerequisites
- Python 3.8+
- MySQL Server
- Apache Kafka & Zookeeper
- Required Python packages:
```bash
pip install -r requirements.txt
```
## 2. Start Kafka and Zookeper
```bash
# In separate terminals
bin/zookeeper-server-start.sh config/zookeeper.properties
bin/kafka-server-start.sh config/server.properties
```
## 3. Launch Components
```bash
# Terminal 1: AD_Registry
python AD_Registry.py <PORT Registry>

# Terminal 2: AD_Engine
python AD_Engine.py 8081 5 localhost:9092

# Terminal 3+: One per drone
python AD_Drone.py <IP Engine>:<PORT Engine> localhost:9092 <IP Registry>:<PORT Registry> <OPTION> <ID Drone>:<NAME Drone>
python AD_Drone.py <IP Engine>:<PORT Engine> <IP Registry>:<PORT Registry> <OPTION> <ID Drone>:<NAME Drone>
# etc...

# Terminal X: Web frontend
python front.py
```
Then open `https://<your_ip>:5004/front` in a browser.

---

# 🎨 Visualization Options
- Pygame GUI: Shows drone positions with IDs and statuses (N, Y, X)
- Web UI: Displays drone map, temperature, and activity logs

---

# 🔑 Security
- TLS: All socket and HTTPS communication is encrypted
- Token Auth: Drones register and authenticate using unique tokens
- Symmetric Encryption: Kafka messages are encrypted using Fernet keys

---

# 🛠️ Configuration
- `AwD_figuras.json`: Define formations and scheduling
- `ciudades.json`: Weather monitoring location
- `openweather_key.txt`: API key for OpenWeather

---

# 📋 Example Commands
Register a drone via API and join the show:
```bash
python AD_Drone.py localhost:8081 localhost:9092 localhost:8082 -raea 3:charlie
```
---
Register only:
```bash
python AD_Drone.py localhost:8081 localhost:9092 localhost:8082 -ra 4:delta
```
---
Join show only:
```bash
python AD_Drone.py localhost:8081 localhost:9092 localhost:8082 -ea 4:delta
```
