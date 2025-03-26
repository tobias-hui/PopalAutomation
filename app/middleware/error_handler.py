from fastapi import Request, Response
from fastapi.responses import JSONResponse
from app.config.settings import ERROR_MESSAGES
import logging

logger = logging.getLogger(__name__)

async def error_handler_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={"error": str(e)}
        )
    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        return JSONResponse(
            status_code=404,
            content={"error": ERROR_MESSAGES['FILE_NOT_FOUND']}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        ) 