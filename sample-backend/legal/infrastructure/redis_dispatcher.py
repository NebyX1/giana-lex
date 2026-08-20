from uuid import UUID

from redis import Redis


class RedisStreamWorkflowDispatcher:
    def __init__(self, redis_url: str, stream_name: str = "giana:legal:commands"):
        if not redis_url:
            raise ValueError("REDIS_URL is required for the Redis workflow dispatcher")
        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.stream_name = stream_name

    def dispatch(self, command_id: UUID) -> None:
        self.client.xadd(self.stream_name, {"command_id": str(command_id)})
