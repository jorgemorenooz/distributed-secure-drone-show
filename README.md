# Distributed Secure Drone Show

<p align="center">
  <img src="https://i.pinimg.com/originals/bc/f3/a3/bcf3a371b9303c27752e1109e96a2fe6.gif" alt="Drone GIF">
</p>

🛰️ Art with Drones
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
