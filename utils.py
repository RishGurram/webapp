# Rest framework imports
from fastapi.responses import JSONResponse


def response(status: bool, message: str, status_code: int, data=None, headers=None):
    """
    Customize the response for better information delivery.

    :param status: True if the response if for successful api response else False
    :param message: String message to give details
    :param status_code: states code of the response
    :param data: send data if any
    :param headers: provide headers in the response
    :return: Response class object
    """
    if headers is None:
        headers = {}
    return JSONResponse(content={
        "status": "success" if status else "error",
        "message": message,
        "data": data if status else None
    }, status_code=status_code, headers=headers, media_type="application/json")