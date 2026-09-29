from channels.generic.websocket import AsyncWebsocketConsumer
import json

class DashboardConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.groupname = "realtime"

        print("ADDING TO GROUP...")

        await self.channel_layer.group_add(
            self.groupname,
            self.channel_name
        )

        print("ADDED TO GROUP")

        await self.accept()

        print("WEBSOCKET ACCEPTED")

    async def disconnect(self, close_code):
        print("DISCONNECTED:", close_code)

        await self.channel_layer.group_discard(
            self.groupname,
            self.channel_name
        )

    async def receive(self, text_data):
        print("RECEIVED:", text_data)
        
        datapoint = json.loads(text_data)
        val = datapoint['value']

        await self.channel_layer.group_send(
            self.groupname,
            {
                'type': 'deprocessing',
                'value': val
            }
        )
        
    
    async def deprocessing(self, event):
        valOther = event['value']
        await self.send(text_data=json.dumps({'value': valOther}))

class VoteConsumer(AsyncWebsocketConsumer):

    votes = {}

    async def connect(self):

        self.groupname = "real_time_vote"

        print(f"ADDING {self.channel_name} TO {self.groupname}")

        await self.channel_layer.group_add(
            self.groupname,
            self.channel_name
        )

        print("ADDED TO GROUP")

        await self.accept()

        print("VOTE WEBSOCKET ACCEPTED")

        await self.send(
            text_data=json.dumps({
                "type": "vote_update",
                "votes": self.votes
            })
        )

    async def disconnect(self, close_code):

        print(
            f"{self.groupname} has been disconnected "
            f"with status code {close_code}"
        )

        await self.channel_layer.group_discard(
            self.groupname,
            self.channel_name
        )

    async def receive(self, text_data):

        print("VOTE RECEIVED:", text_data)

        datapoint = json.loads(text_data)

        if isinstance(datapoint, dict):
            incoming_votes = datapoint.get("votes", {})
            candidate = datapoint.get("candidate")
            print(incoming_votes, candidate)

            if isinstance(incoming_votes, dict):
                for key, value in incoming_votes.items():
                    self.votes[str(key)] = int(value)

            if candidate:
                candidate_key = str(candidate)
                if candidate_key not in self.votes:
                    self.votes[candidate_key] = 0
                self.votes[candidate_key] += 1

        print("UPDATED VOTES:", self.votes)

        await self.channel_layer.group_send(
            self.groupname,
            {
                "type": "vote_update",
                "votes": self.votes
            }
        )

    async def vote_update(self, event):

        print("BROADCASTING:", event)

        await self.send(
            text_data=json.dumps({
                "type": "vote_update",
                "votes": event["votes"],
                "vote": event.get("vote"),
            })
        )
        
class VoteConsumer2(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = "vote_results"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        print("Disconnected")
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def vote_update(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "vote_update",
                "votes": event["votes"]
            })
        )