import logging
import os
import time
from uuid import UUID

from redis import Redis
from redis.exceptions import ResponseError

from app import create_app
from app.extensions import db
from legal.workflows.engine import DurableWorkflowEngine
from legal.infrastructure.models import CaseCommandRecord
from legal.infrastructure.outbox import OutboxPublisher
from legal.infrastructure.redis_dispatcher import RedisStreamWorkflowDispatcher


logger = logging.getLogger(__name__)


def run_worker() -> None:
    app = create_app(os.getenv("FLASK_CONFIG", "production"))
    redis_url = app.config["REDIS_URL"]
    if not redis_url:
        raise RuntimeError("REDIS_URL is required by the legal workflow worker")
    client = Redis.from_url(redis_url, decode_responses=True)
    stream = app.config["LEGAL_REDIS_STREAM"]
    group = app.config["LEGAL_REDIS_CONSUMER_GROUP"]
    consumer = app.config["LEGAL_REDIS_CONSUMER_NAME"]
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    with app.app_context():
        outbox = OutboxPublisher(
            RedisStreamWorkflowDispatcher(redis_url, stream),
            app.config["LEGAL_OUTBOX_MAX_ATTEMPTS"],
        )
        outbox.publish_pending()
        authority_provider = app.extensions.get("legal_authority_provider")
        DurableWorkflowEngine(authority_provider=authority_provider).resume_incomplete_runs()
        while True:
            client.setex(
                app.config["LEGAL_WORKER_HEARTBEAT_KEY"],
                app.config["LEGAL_WORKER_HEARTBEAT_TTL_SECONDS"],
                consumer,
            )
            outbox.publish_pending()
            claimed = client.xautoclaim(
                stream,
                group,
                consumer,
                min_idle_time=app.config["LEGAL_WORKER_CLAIM_IDLE_MS"],
                start_id="0-0",
                count=10,
            )
            messages = [(stream, claimed[1])] if claimed[1] else []
            if not messages:
                messages = client.xreadgroup(group, consumer, {stream: ">"}, count=10, block=5000)
            for _, entries in messages:
                for message_id, fields in entries:
                    command = db.session.get(CaseCommandRecord, fields["command_id"])
                    if command is None:
                        logger.error("Unknown legal command", extra={"message_id": message_id})
                        client.xack(stream, group, message_id)
                        continue
                    if command.attempts >= app.config["LEGAL_WORKER_MAX_RETRIES"]:
                        logger.error("Legal command exhausted retries", extra={"command_id": command.id})
                        client.xack(stream, group, message_id)
                        continue
                    lock = client.lock(
                        f"giana:legal:case:{command.case_id}:lock",
                        timeout=app.config["LEGAL_CASE_LOCK_TTL_SECONDS"],
                        blocking_timeout=1,
                    )
                    try:
                        if lock.acquire():
                            DurableWorkflowEngine(authority_provider=authority_provider).process_command(UUID(fields["command_id"]))
                            client.xack(stream, group, message_id)
                    except Exception:
                        logger.exception("Legal workflow command failed", extra={"message_id": message_id})
                        time.sleep(min(2 ** max(command.attempts, 1), 60))
                    finally:
                        if lock.owned():
                            lock.release()
            time.sleep(0.05)


if __name__ == "__main__":
    run_worker()
