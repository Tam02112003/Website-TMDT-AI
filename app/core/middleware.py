from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import uuid
from core.app_config import logger
from core.context import request_id_ctx

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request_id_ctx.set(request_id)
        request.state.request_id = request_id # Add request_id to request.state
        request.scope["_request_id"] = request_id # Add request_id to request.scope

        # Log the request before processing
        logger.info(f"Request: {request.method} {request.url} - Request ID: {request_id}")

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Extract endpoint function name for logging
        endpoint = request.scope.get('endpoint')
        function_name = getattr(endpoint, '__name__', 'N/A') if endpoint else 'N/A'

        # Log the response after processing, including the function name
        logger.info(f"Response: {response.status_code} - Request ID: {request_id} - Endpoint: {function_name}")
        return response

def setup_middleware(app):
    app.add_middleware(RequestIdMiddleware)