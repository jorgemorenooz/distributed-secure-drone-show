# Distributed Secure Drone Show

<p align="center">
  <img src="https://i.pinimg.com/originals/bc/f3/a3/bcf3a371b9303c27752e1109e96a2fe6.gif" alt="Drone GIF">
</p>

## Table of Contents

- [Introduction](#introduction)
- [Implementation](#implementation)
  - [Engine](#engine)
  - [Drone Authentication](#drone-authentication)
  - [Channel Encryption (Drones)](#channel-encryption-drones)
  - [Audit Logging](#audit-logging)
  - [API_Engine](#api_engine)
  - [Registry](#registry)
  - [Drones](#drones)
  - [Frontend](#frontend)
- [Deployment Guide](#deployment-guide)

---

## Introduction
The goal of this project is to implement:

- A **Service Oriented Architecture (SOA)** using REST services.
- Core **security principles**.

The system:

- **Consumes an existing REST API**.
- **Creates and exposes its own REST API** from the backend to the frontend.
- Implements **three security features**:
  - **Channel encryption**
  - **Secure authentication**
  - **Audit logging**

This project is based on a previous assignment, reusing and improving existing functionality.

---

## Implementation

### Engine

#### Weather REST API

The `AD_Engine` consumes the **OpenWeather API** to obtain weather data for the city where the drone show is performed.

Temperature data is stored and used to trigger automatic actions:

```python
if int(temperature) < 0:
    dronesRETREAT()
