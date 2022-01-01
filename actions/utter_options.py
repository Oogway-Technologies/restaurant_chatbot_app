from typing import Text, Dict, Any, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from const import CLASS_FILTERS, ENTITY_OPTIONS


class ActionUtterOptions(Action):

    def name(self) -> Text:
        return "action_utter_options"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        option_submessages = []
        for filter_str in CLASS_FILTERS:
            title_str = filter_str.replace('_', ' ').title() + ' Options:\n\t'
            options_str = '\n\t'.join(f"- {option.replace('_', ' ')}" for option in ENTITY_OPTIONS[filter_str])
            option_submessages.append(title_str + options_str)
        dispatcher.utter_message('\n\t'.join(option_submessages))
        return []
