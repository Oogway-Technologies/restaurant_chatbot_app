import logging
from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from const import (RASA_ENTITIES_LIST, FILTER_KEY,
                   RASA_ENTITY_TYPE, RASA_ENTITY_VALUE, RASA_ENTITY_ROLE,
                   RASA_ENTITY_RAW, RASA_ENTITY_CLASS, RASA_ENTITY_OPERATOR,
                   CLASS_FILTERS, RAW_FILTERS)


class ActionRemovePreference(Action):

    def name(self) -> Text:
        return "action_remove_preference"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        filters_to_remove = []
        # Get the type of entity and break if it doesn't correspond to a supported slot type
        for entity in tracker.latest_message[RASA_ENTITIES_LIST]:
            entity_type = entity[RASA_ENTITY_TYPE]
            if entity_type != FILTER_KEY:
                continue

            # TODO: Use this to when asking the user to approve that this raw text was understood correctly
            # Get the raw text that was extracted for that entity
            raw_entity = entity[RASA_ENTITY_VALUE]

            # If there is a role, set it as a filter to remove
            if RASA_ENTITY_ROLE in entity.keys():
                filters_to_remove.append(entity[RASA_ENTITY_ROLE])
            else:
                logging.warning(f'No role set for "{entity_type}" entity: "{raw_entity}"')

        n_filters_to_remove = len(filters_to_remove)
        if n_filters_to_remove == 0:
            message = "I didn't detect any filters to remove."
        elif n_filters_to_remove == 1:
            message = f'Removed the "{filters_to_remove[0]}" filter.'
        else:   # n_filters_t  o_remove > 1
            message = f'Removed the following filters: {filters_to_remove}'

        dispatcher.utter_message(message)

        slot_update_events = get_filter_removal_events(filters_to_remove)

        return slot_update_events


def get_filter_removal_events(filters_to_remove):
    slot_update_events = []
    for entity_type in filters_to_remove:
        if entity_type in RAW_FILTERS:
            slot_update_events.append(SlotSet(entity_type, None))
        elif entity_type in CLASS_FILTERS:
            slot_update_events.append(SlotSet(entity_type + RASA_ENTITY_RAW, None))
            slot_update_events.append(SlotSet(entity_type + RASA_ENTITY_CLASS, None))
            slot_update_events.append(SlotSet(entity_type + RASA_ENTITY_OPERATOR, None))
        else:
            logging.warning(f'Unexpected entity_type: {entity_type}')
    return slot_update_events
