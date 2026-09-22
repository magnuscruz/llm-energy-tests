import asyncio, os, sys, time
from tapo import ApiClient

async def monitor():
    client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
    device = await client.p115(os.environ['TAPO_IP'])
    print('timestamp,power_w')
    sys.stdout.flush()
    while True:
        energy = await device.get_current_power()
        print(f'{int(time.time())},{energy.current_power}')
        sys.stdout.flush()
        await asyncio.sleep(1)

asyncio.run(monitor())
