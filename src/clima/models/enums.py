from enum import StrEnum


class Theme(StrEnum):
    LIGHT = "LIGHT"
    DARK = "DARK"


class Season(StrEnum):
    WINTER = "WINTER"
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    AUTUMN = "AUTUMN"


class ItemPart(StrEnum):
    TOP = "TOP"
    BOTTOM = "BOTTOM"
    SHOES = "SHOES"
    ACCESSORY = "ACCESSORY"
    ONE_PIECE = "ONE_PIECE"


class Actions:
    RATE = "rate"
    SAVE = "save"
    ADD_FAVORITE = "addFavorite"
    REMOVE_FAVORITE = "removeFavorite"
    OPEN_FAVORITE = "openFavorite"
    REPLACE_ITEM = "replaceItem"
    SELECT_ITEMS = "selectItems"
    SELECT_OUTFIT = "selectOutfit"
    EDIT_ITEM = "editItem"
    EDIT_PHOTO = "editPhoto"
    DELETE_ITEM = "deleteItem"
    MARK_LAUNDRY = "markLaundry"
    SET_THEME = "setTheme"
    SET_NOTIFICATION = "setNotification"
    DELETE_ACCOUNT = "deleteAccount"
    CONFIRM_DELETE = "confirmDelete"
    CMD_START = "/start"
    CMD_REGISTER = "/register"
    CMD_LOGIN = "/login"
    CMD_PROFILE = "/profile"
    CMD_PROFILE_SAVE = "/profile/save"
    CMD_HISTORY = "/history"

    @staticmethod
    def getAction(name: str) -> str:
        return name
