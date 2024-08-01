from enum import IntEnum, auto

from enum import Enum


class ConversationState(Enum):
    # MainMenu
    CHANGE_SETTINGS = 0
    MANAGE_APPS = 1
    UNSUSPEND_APP = 2
    MANAGE_APPS_OPTIONS = 3
    LIST_APPS = 4

    # AddApp
    SEND_LINK = 5
    SEND_LINK_FROM_EDIT = 6
    SEND_LINK_FROM_REMOVE = 7
    CONFIRM_APP_NAME = 8
    ADD_OR_EDIT_FINISH = 9

    # SetApp
    SET_INTERVAL = 10
    CONFIRM_INTERVAL = 11
    SEND_ON_CHECK = 12
    SET_UP_ENDED = 13

    # EditApp
    EDIT_SELECT_APP = 14
    EDIT_CONFIRM_APP = 15
    EDIT_NO_APPS = 16

    # DeleteApp
    DELETE_APP_SELECT = 17
    DELETE_APP_CONFIRM = 18

    TO_BE_ENDED = 19
