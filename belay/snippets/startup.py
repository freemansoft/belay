def __belay(f):
    def belay_interface(*args, **kwargs):
        print("_BELAYR" + repr(f(*args, **kwargs)))
    globals()["_belay_" + f.__name__] = belay_interface
    return f
