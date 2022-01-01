import logging
import requests
import time
from typing import Text, Dict, Any, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.executor import CollectingDispatcher

from const import QA_LOADING_COUNTER, HUGGING_FACE_KEY

GENERATED_TEXT = 'generated_text'
QA_ACTION_NAME = 'action_qa_answer'
INTERVAL_LENGTH = 5     # 5 seconds
N_INTERVALS = 30


class ActionProcessPreferences(Action):

    def name(self) -> Text:
        return QA_ACTION_NAME

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        API_URL = "https://api-inference.huggingface.co/models/allenai/macaw-large"
        # API_URL = "https://api-inference.huggingface.co/models/allenai/macaw-answer-11b"
        headers = {"Authorization": "Bearer " + HUGGING_FACE_KEY}

        def query(payload):
            response = requests.post(API_URL, headers=headers, json=payload)
            return response.json()

        qa_loading_counter = tracker.get_slot(QA_LOADING_COUNTER)
        if qa_loading_counter > 0:
            time.sleep(INTERVAL_LENGTH)

        output = query({f"inputs": "$answer$ ; $question$ = " + tracker.latest_message['text']})
        success = isinstance(output, list) and len(output) == 1 and output[0].keys() == set([GENERATED_TEXT])
        failure = isinstance(output, dict) and 'error' in output.keys()

        if success:
            generated_text = output[0][GENERATED_TEXT]
            expected_start = '$answer$ = '
            assert generated_text.startswith(expected_start)
            answer = generated_text[len(expected_start):]
            dispatcher.utter_message(answer)
            return [SlotSet(QA_LOADING_COUNTER, 0)]
        elif failure:
            qa_loading_counter = tracker.get_slot(QA_LOADING_COUNTER)
            if qa_loading_counter == 0:
                dispatcher.utter_message('Thinking...')
                return [SlotSet(QA_LOADING_COUNTER, qa_loading_counter + 1), FollowupAction(QA_ACTION_NAME)]
            if qa_loading_counter < N_INTERVALS:
                return [SlotSet(QA_LOADING_COUNTER, qa_loading_counter + 1), FollowupAction(QA_ACTION_NAME)]
            else:   # qa_loading_counter >= N_INTERVALS:
                dispatcher.utter_message("Hmm, I don't seem to be able to think quickly enough right now.")
                return [SlotSet(QA_LOADING_COUNTER, 0)]
        else:
            logging.warning('Unexpected case where both "success" and "failure" are False')
            return [SlotSet(QA_LOADING_COUNTER, 0)]
