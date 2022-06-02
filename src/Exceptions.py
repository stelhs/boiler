from sr90Exceptions import *



class BoilerError(AppError):
    pass

# Skynet notifier client errors

class SkynetNotifierError(AppError):
    pass

class SkynetNotifierConnectionError(SkynetNotifierError):
    pass

class SkynetNotifierSendError(SkynetNotifierError):
    pass

class SkynetNotifierResponseError(SkynetNotifierError):
    pass


