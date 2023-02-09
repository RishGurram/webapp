# Rest framework imports
from fastapi.responses import JSONResponse, Response
from fastapi import status as st


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

    
    
    message = message if type(message) in [dict, list] else {"message":message}

    if status_code == st.HTTP_204_NO_CONTENT:
        return Response(status_code=status_code, headers=headers, media_type="application/json")
    return JSONResponse(content=data if data else message
    , status_code=status_code, headers=headers, media_type="application/json")