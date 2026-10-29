import asyncio, os, sys, time
from tapo import ApiClient

async def monitor():
    client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
    device = await client.p115(os.environ['TAPO_IP'])
    print('timestamp,power_w')
    sys.stdout.flush()
    while True:
        try:
            energy = await device.get_current_power()
            print(f'{time.time():.3f},{energy.current_power}')
            sys.stdout.flush()
        except Exception as e:
            print(f'err,{e}', file=sys.stderr)
        await asyncio.sleep(1)

asyncio.run(monitor())
