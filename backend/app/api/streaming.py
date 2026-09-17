"""即使发送中断或生成器尚未启动，也终结流式请求的预扣。"""
from anyio import CancelScope
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from app.services.quota_reservation_service import QuotaReservationService


class QuotaStreamingResponse(StreamingResponse):
    def __init__(self, source, engine, reservation_id, on_close=None):
        super().__init__(source, media_type='text/event-stream')
        self.source = source
        self.sessions = sessionmaker(bind=engine)
        self.reservation_id = reservation_id
        self.on_close = on_close

    def release(self):
        try:
            with self.sessions() as db:
                QuotaReservationService(db).release(self.reservation_id)
        finally:
            if self.on_close:
                self.on_close()

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with CancelScope(shield=True):
                try:
                    if hasattr(self.source, 'aclose'):
                        await self.source.aclose()
                    else:
                        await run_in_threadpool(self.source.close)
                finally:
                    await run_in_threadpool(self.release)
