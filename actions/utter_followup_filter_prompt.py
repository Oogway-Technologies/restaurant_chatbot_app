import random
from typing import Text, Dict, Any, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from const import CLASS_FILTERS, RASA_ENTITY_CLASS, FILTER_TYPE_TO_NEXT_PAYLOAD


class ActionUtterFollowupFilterPrompt(Action):

    def name(self) -> Text:
        return "action_utter_followup_filter_prompt"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        unspecified_filters = [filter_base for filter_base in CLASS_FILTERS
                               if tracker.get_slot(filter_base + RASA_ENTITY_CLASS) is None]
        if len(unspecified_filters) == 0:
            done_phrases = [
                "I can't accept any other types of information now.",
                "You've given me all the information I currently support.",
                "That's all the different types of info I can accept right now.",
            ]
            meme_images = [
                # Funny faces from having too much information
                'https://i.imgflip.com/gfos9.jpg',   # woman
                'https://i.imgflip.com/lh1o4.jpg',  # cat
                'https://media.makeameme.org/created/information-you-give.jpg',     # Yoda
                # 'https://memegenerator.net/img/instances/81413328.jpg',     # bird

                # Memes that tell the user to stop
                # 'https://memegenerator.net/img/instances/69659362.jpg',  # Kevin Hart
                # 'https://www.memecreator.org/static/images/memes/3760299.jpg',  # Obama

                # Memes that make it unclear if there is too much or not enough info
                # 'https://memegenerator.net/img/instances/62575006.jpg', # Not sure meme
                # 'https://i.imgflip.com/2pyrwc.jpg',  # Dwight (The Office)

                # History channel guy (doesn't seem to work in the bot; this is a site that runs captchas)
                # 'https://hamilbrosstudios.com/wp-content/uploads/2017/01/14_too-much-info.jpg',
            ]
            dispatcher.utter_message(random.choice(done_phrases), image=random.choice(meme_images))
        else:
            # TODO: consider not going through these or doing it 2 times
            # Choose the next 2 filters in the order and randomly choose the other 2
            # Python automatically handles the case where the list length is less than 3t
            n_deterministic_filters = 2
            n_random_filters = 2
            next_filters = unspecified_filters[:n_deterministic_filters]
            random_filters_population = unspecified_filters[n_deterministic_filters:]
            filters_to_show = next_filters + random.sample(random_filters_population,
                                                           k=min(n_random_filters, len(random_filters_population)))

            # Create the buttons and message and send
            buttons = [{'title': filter_base.replace('_', ' '), 'payload': FILTER_TYPE_TO_NEXT_PAYLOAD[filter_base]}
                       for filter_base in filters_to_show]
            prompt_phrases = [
                "Any other restaurant preferences you'd like to give me?",
                'Other restaurant preferences?',
                'What else should I know to help find you the perfect restaurant?',
                'Any other restaurant info I should factor in?'
            ]
            dispatcher.utter_message(random.choice(prompt_phrases), buttons=buttons)

        return []
