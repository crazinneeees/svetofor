from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
from typing import List, Optional
import uvicorn
from datetime import datetime

app = FastAPI()


# Управление светофором
class TrafficLightManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.controller: Optional[WebSocket] = None
        self.current_color: str = "none"  # none, red, yellow, green
        self.controller_id: Optional[str] = None

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)

        # Первый подключившийся становится контроллером
        is_controller = self.controller is None
        if is_controller:
            self.controller = websocket
            self.controller_id = user_id
        await self.send_state_update(websocket, is_controller)
        await self.broadcast_user_update()
        return is_controller

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

            # Если контроллер отключился, назначаем нового
            if websocket == self.controller:
                self.controller = None
                self.controller_id = None

                # Назначаем первого из оставшихся контроллером
                if self.active_connections:
                    self.controller = self.active_connections[0]
                    # Уведомляем нового контроллера
                    return True
        return False

    async def send_state_update(self, websocket: WebSocket, is_controller: bool):
        state_data = {
            "type": "state_update",
            "color": self.current_color,
            "is_controller": is_controller,
            "controller_id": self.controller_id,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        try:
            await websocket.send_text(json.dumps(state_data))
        except:
            pass

    async def broadcast_color_change(self, color: str):
        self.current_color = color
        color_data = {
            "type": "color_change",
            "color": color,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(color_data))
            except:
                self.active_connections.remove(connection)

    async def broadcast_user_update(self):
        user_data = {
            "type": "user_update",
            "total_users": len(self.active_connections),
            "controller_id": self.controller_id
        }

        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(user_data))
            except:
                pass

    async def broadcast_new_controller(self):
        if self.controller:
            await self.send_state_update(self.controller, True)
            for connection in self.active_connections:
                if connection != self.controller:
                    await self.send_state_update(connection, False)


traffic_manager = TrafficLightManager()


@app.get("/")
async def get():
    return HTMLResponse(content=html_content, status_code=200)


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    is_controller = await traffic_manager.connect(websocket, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Только контроллер может менять цвета
            if message_data["type"] == "color_change" and websocket == traffic_manager.controller:
                color = message_data["color"]
                if color in ["red", "yellow", "green", "none"]:
                    await traffic_manager.broadcast_color_change(color)

    except WebSocketDisconnect:
        new_controller_assigned = traffic_manager.disconnect(websocket)
        if new_controller_assigned:
            await traffic_manager.broadcast_new_controller()
        await traffic_manager.broadcast_user_update()


@app.get("/status")
async def get_status():
    return {
        "current_color": traffic_manager.current_color,
        "total_users": len(traffic_manager.active_connections),
        "controller_id": traffic_manager.controller_id
    }



html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Умный Светофор</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            color: white;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .status-info {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }

        .login-form {
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            text-align: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }

        .login-form h2 {
            margin-bottom: 20px;
            font-size: 1.8em;
        }

        .login-form input {
            padding: 12px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            width: 300px;
            max-width: 100%;
            margin-bottom: 20px;
            text-align: center;
        }

        .login-form button {
            padding: 12px 30px;
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }

        .login-form button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }

        .traffic-light-container {
            display: none;
            flex-direction: column;
            align-items: center;
            gap: 30px;
        }

        .traffic-light-container.active {
            display: flex;
        }

        .traffic-light {
            background: #2c3e50;
            border-radius: 25px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border: 5px solid #34495e;
        }

        .light {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            margin: 15px;
            border: 3px solid rgba(255,255,255,0.3);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .light::before {
            content: '';
            position: absolute;
            top: 20%;
            left: 20%;
            width: 30%;
            height: 30%;
            background: rgba(255,255,255,0.3);
            border-radius: 50%;
            transition: all 0.3s ease;
        }

        .light.red {
            background: #e74c3c;
            box-shadow: 0 0 30px #e74c3c, inset 0 0 30px rgba(255,255,255,0.2);
        }

        .light.yellow {
            background: #f1c40f;
            box-shadow: 0 0 30px #f1c40f, inset 0 0 30px rgba(255,255,255,0.2);
        }

        .light.green {
            background: #27ae60;
            box-shadow: 0 0 30px #27ae60, inset 0 0 30px rgba(255,255,255,0.2);
        }

        .light.off {
            background: #7f8c8d;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.3);
        }

        .controls {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            justify-content: center;
        }

        .control-btn {
            padding: 15px 25px;
            border: none;
            border-radius: 15px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            min-width: 120px;
        }

        .control-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }

        .control-btn:active {
            transform: translateY(0);
        }

        .control-btn.red {
            background: linear-gradient(45deg, #e74c3c, #c0392b);
            color: white;
        }

        .control-btn.yellow {
            background: linear-gradient(45deg, #f1c40f, #d68910);
            color: #2c3e50;
        }

        .control-btn.green {
            background: linear-gradient(45deg, #27ae60, #1e8449);
            color: white;
        }

        .control-btn.off {
            background: linear-gradient(45deg, #95a5a6, #7f8c8d);
            color: white;
        }

        .user-info {
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }

        .controller-badge {
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
            display: inline-block;
            margin-top: 10px;
            animation: pulse 2s infinite;
        }

        .observer-badge {
            background: rgba(255,255,255,0.2);
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 14px;
            display: inline-block;
            margin-top: 10px;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }

        .connection-status.connected {
            background: rgba(39, 174, 96, 0.8);
            color: white;
        }

        .connection-status.disconnected {
            background: rgba(231, 76, 60, 0.8);
            color: white;
        }

        @media (max-width: 768px) {
            .light {
                width: 80px;
                height: 80px;
            }

            .controls {
                flex-direction: column;
                align-items: center;
            }

            .control-btn {
                width: 80%;
                max-width: 300px;
            }
        }
    </style>
</head>
<body>
    <div class="connection-status" id="connectionStatus">Ulanmagan</div>

    <div class="header">
        <h1>🚦 Aqlli svetofor</h1>
        <div class="status-info">
            <div>Ulangan devicelar: <span id="userCount">0</span></div>
            <div>Boshqaruvchi: <span id="controllerName">Hech kim</span></div>
        </div>
    </div>

    <div class="login-form" id="loginForm">
        <h2>Svetoforga ulanish</h2>
        <input type="text" id="usernameInput" placeholder="Ismingizni kiriting" maxlength="20">
        <button onclick="connectToTrafficLight()">Ulanish</button>
    </div>

    <div class="traffic-light-container" id="trafficLightContainer">
        <div class="traffic-light">
            <div class="light off" id="redLight"></div>
            <div class="light off" id="yellowLight"></div>
            <div class="light off" id="greenLight"></div>
        </div>

        <div class="controls" id="controls" style="display: none;">
            <button class="control-btn red" onclick="changeColor('red')">Qizil</button>
            <button class="control-btn yellow" onclick="changeColor('yellow')">Sariq</button>
            <button class="control-btn green" onclick="changeColor('green')">Yashil</button>
            <button class="control-btn off" onclick="changeColor('none')">O'chirish</button>
        </div>

        <div class="user-info" id="userInfo">
            <div>Sizning ismingiz: <strong id="userName"></strong></div>
            <div id="userRole"></div>
        </div>
    </div>

    <script>
        let ws = null;
        let currentUser = "";
        let isController = false;

        function connectToTrafficLight() {
            const username = document.getElementById('usernameInput').value.trim();
            if (!username) {
                alert('Iltimos, ismingizni kiriting');
                return;
            }

            currentUser = username;
            const wsUrl = `ws://${window.location.host}/ws/${encodeURIComponent(username)}`;

            ws = new WebSocket(wsUrl);

            ws.onopen = function(event) {
                document.getElementById('loginForm').style.display = 'none';
                document.getElementById('trafficLightContainer').classList.add('active');
                document.getElementById('userName').textContent = currentUser;
                updateConnectionStatus('connected');
            };

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);

                switch(data.type) {
                    case 'state_update':
                        isController = data.is_controller;
                        updateLights(data.color);
                        updateUserRole(data.is_controller);
                        break;

                    case 'color_change':
                        updateLights(data.color);
                        break;

                    case 'user_update':
                        document.getElementById('userCount').textContent = data.total_users;
                        document.getElementById('controllerName').textContent = data.controller_id || 'Hech kim';
                        break;
                }
            };

            ws.onclose = function(event) {
                updateConnectionStatus('disconnected');
                setTimeout(() => {
                    if (ws.readyState === WebSocket.CLOSED) {
                        connectToTrafficLight();
                    }
                }, 3000);
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                updateConnectionStatus('disconnected');
            };
        }

        function changeColor(color) {
            if (ws && ws.readyState === WebSocket.OPEN && isController) {
                ws.send(JSON.stringify({
                    type: 'color_change',
                    color: color
                }));
            }
        }

        function updateLights(color) {
            const redLight = document.getElementById('redLight');
            const yellowLight = document.getElementById('yellowLight');
            const greenLight = document.getElementById('greenLight');

            // Сбрасываем все цвета
            redLight.className = 'light off';
            yellowLight.className = 'light off';
            greenLight.className = 'light off';

            // Включаем нужный цвет
            if (color === 'red') {
                redLight.className = 'light red';
            } else if (color === 'yellow') {
                yellowLight.className = 'light yellow';
            } else if (color === 'green') {
                greenLight.className = 'light green';
            }
        }

        function updateUserRole(isCtrl) {
            const roleElement = document.getElementById('userRole');
            const controlsElement = document.getElementById('controls');

            if (isCtrl) {
                roleElement.innerHTML = '<div class="controller-badge">🎮 Boshqaruvchi</div>';
                controlsElement.style.display = 'flex';
            } else {
                roleElement.innerHTML = '<div class="observer-badge">👀 Kuzatuvchi</div>';
                controlsElement.style.display = 'none';
            }
        }

        function updateConnectionStatus(status) {
            const statusElement = document.getElementById('connectionStatus');
            statusElement.className = `connection-status ${status}`;
            statusElement.textContent = status === 'connected' ? '🟢 Ulangan' : '🔴 Ulanmagan';
        }

        // Обработка клавиш для контроллера
        document.addEventListener('keydown', function(e) {
            if (!isController) return;

            switch(e.key) {
                case '1':
                    changeColor('red');
                    break;
                case '2':
                    changeColor('yellow');
                    break;
                case '3':
                    changeColor('green');
                    break;
                case '0':
                    changeColor('none');
                    break;
            }
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    # Запуск на всех интерфейсах для доступа из локальной сети
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)