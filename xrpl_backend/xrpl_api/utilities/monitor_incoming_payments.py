import asyncio
import websockets
import json

# Handles incoming messages
async def handler(websocket):
    message = await websocket.recv()
    return message

# Use this to send API requests
async def api_request(options, websocket):
    try:
        await websocket.send(json.dumps(options))
        message = await websocket.recv()
        return json.loads(message)
    except Exception as e:
        return e

# Tests functionality of API_Requst
async def pingpong(websocket):
    command = {
        "id": "on_open_ping_1",
        "command": "ping"
    }
    value = await api_request(command, websocket)
    print(value)

async def do_subscribe(websocket):
    command = await api_request({
        'command': 'subscribe',
        'accounts': ['rBKnvchY2NwDj1bufNUB61KXGnpPTMZ1Mm']
        }, websocket)

    if command['status'] == 'success':
        print('Successfully Subscribed!')
    else:
        print("Error subscribing: ", command)
    print('Received message from server', await handler(websocket))

async def run():
    # Opens connection to ripple testnet
    async for websocket in websockets.connect('wss://s.altnet.rippletest.net:51233'):
        try:
           await pingpong(websocket)
           await do_subscribe(websocket)
        except websockets.ConnectionClosed:
            print('Disconnected...')

# Runs the webhook on a loop
def main():
    asyncio.run(run())
    print('Restarting Loop')

if __name__ == '__main__':
    main()