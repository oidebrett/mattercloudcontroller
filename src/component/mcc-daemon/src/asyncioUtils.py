import asyncio
import sys 
import json
import aiohttp


class MemQueue(asyncio.Queue):
    def __init__(self, maxsize=0, maxmemsize=0,refresh_interval=1.0, refresh_timeout=60):
        super().__init__(maxsize)
        self.maxmemsize = maxmemsize
        self.refresh_interval = refresh_interval
        self.refresh_timeout = refresh_timeout

    async def put(self, item):
        item_size = sys.getsizeof(item)

    	# specific locking code (see original class in GitHub)
        super().put_nowait((item_size, item))

    def put_nowait(self, item):
        item_size = sys.getsizeof(item)
        
        if self.full(item_size):
            raise asyncio.QueueFull
        super().put_nowait((item_size, item))

class CancellableSleeps:
    def __init__(self):
        self._sleeps = set()

    async def sleep(self, delay, result=None, *, loop=None):
        async def _sleep(delay, result=None, *, loop=None):
            coro = asyncio.sleep(delay, result=result)
            task = asyncio.ensure_future(coro)
            self._sleeps.add(task)
            try:
                return await task
            except asyncio.CancelledError:
                print("Sleep canceled")
                return result
            finally:
                self._sleeps.remove(task)

        await _sleep(delay, result=result, loop=loop)

    def cancel(self):
        for task in self._sleeps:
            task.cancel()

class TestFileHandler: 
    #This code is to allow for local testing 
    #where it polls for a command that is written into the sample_data.json file
    #this file carries the same json format as that that comes from the MQTT bus

    def loadTestData(self, file_name: str):
        with open(file_name) as f:
            try:
                sample = json.load(f)
                f.close()
                return sample
            except:
                return json.loads('''{}''')

    def clearTestData(self, file_name: str):
        file = open(file_name,"r+")
        file. truncate(0)
        file. close()

    def loadAndCleanTestData(self, file_name: str):
        sample = self.loadTestData(file_name)
        self.clearTestData(file_name)
        return sample

    async def pollForCommand(self, file_name: str, queue: MemQueue):
        sample = self.loadAndCleanTestData(file_name)
        nodeId = None
        try:
            command = sample["command"]
            # add to the queue
            message_object = json.dumps(sample)

            # add to the queue
            await queue.put(message_object)

        except:
            pass

class WebhookHandler:
    async def sendWebhook(self, webhook_method, webhook_url, webhook_endpoint, data, headers):
        async with aiohttp.ClientSession(webhook_url) as session:
            if webhook_method == "POST":
                async with session.post('/'+webhook_endpoint, data=data, headers=headers) as r:
                    text = await r.text()
            elif webhook_method == "GET":
                async with session.get('/'+webhook_endpoint, headers=headers) as r:
                    text = await r.text()

            await session.close()
