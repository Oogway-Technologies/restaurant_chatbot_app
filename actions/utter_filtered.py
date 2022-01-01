from itertools import combinations
import json
import logging
from math import floor
import random
import requests
from typing import Text, Dict, Any, List

from bson import ObjectId, json_util
import pymongo
from pymongo import MongoClient
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.remove_preference import get_filter_removal_events
from const import (RASA_ENTITY_CLASS, RASA_ENTITY_OPERATOR, ATTRIBUTES,
                   CLASS_FILTERS, RAW_FILTERS, ALL_FILTERS,
                   YELP_CATEGORY_ATTRIBUTES, NON_AMENITY_ATTRIBUTES, PRICE,
                   CITY, ZIP_CODE, CUSTOM_FILTER, RESTAURANT_ID,
                   NOT, AND, OR,
                   MONGODB_CREDENTIAL_URL)

MAX_N_RESTAURANTS = 5


class ActionUtterFiltered(Action):

    def name(self) -> Text:
        return "action_utter_filtered"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        self._utter_detected_filters(dispatcher, tracker)
        filter_removal_events = self._retrieve_and_utter_restaurants(dispatcher, tracker)
        if filter_removal_events is None:
            return []
        else:
            return filter_removal_events

    @staticmethod
    def _utter_detected_filters(dispatcher, tracker):
        # Create and send a message with "<entity_type>: [<entity_classes>]" for all supported slots that have been set
        filter_submessages = []

        for filter_str in RAW_FILTERS:
            filter_raws = tracker.get_slot(filter_str)
            if filter_raws is None or filter_raws == []:
                continue

            if len(filter_raws) > 1:
                logic_str = f' (logic: OR)'
            else:
                logic_str = ''
            filter_submessage = f'{filter_str}: {filter_raws}' + logic_str
            filter_submessages.append(filter_submessage)

        for filter_base in CLASS_FILTERS:
            filter_classes = tracker.get_slot(filter_base + RASA_ENTITY_CLASS)
            if filter_classes is None or filter_classes == []:
                continue

            logic_operator = tracker.get_slot(filter_base + RASA_ENTITY_OPERATOR)
            if len(filter_classes) > 1 or logic_operator == NOT:
                logic_str = f' (logic: {logic_operator})'
            else:
                logic_str = ''
            filter_submessage = f'{filter_base}: {filter_classes}' + logic_str
            filter_submessages.append(filter_submessage)

        if len(filter_submessages) == 0:
            filter_message = None
        else:
            filter_message = '\n\t' + '\n\t'.join(filter_submessages)

        dispatcher.utter_message('Recognized filters: {}'.format(filter_message))

    def _retrieve_and_utter_restaurants(self, dispatcher, tracker):
        filter_str_list_and_operator_list = self._get_filter_str_list_and_operator_list(tracker)
        query = self._build_query(filter_str_list_and_operator_list)
        result, n_matches = self._query_db(query)
        if n_matches > 0:
            self._utter_matches(dispatcher, result, n_matches)
        else:
            return self._remove_filters_and_utter_matches(dispatcher, filter_str_list_and_operator_list)

    @staticmethod
    def _get_custom_filter_restaurant_ids(filter_list):
        query = ' '.join(filter_list)
        print('custom query:', query)

        url = "http://3.130.66.102:8000/keyword_search"
        payload = json.dumps({
            "query": query,
            "params": {"top_k": 10000}
        })
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)

        response_dict = json.loads(response.content.decode('utf-8'))
        restaurant_ids = [ObjectId(document['meta']['id']) for document in response_dict['documents']]
        return restaurant_ids

    def _get_filter_str_list_and_operator_list(self, tracker):
        filter_str_list_and_operator_list = []
        for filter_str in ALL_FILTERS:
            if filter_str in CLASS_FILTERS:
                filter_list = tracker.get_slot(filter_str + RASA_ENTITY_CLASS)
                filter_logic_operator = tracker.get_slot(filter_str + RASA_ENTITY_OPERATOR)
            elif filter_str in RAW_FILTERS:
                filter_list = tracker.get_slot(filter_str)
                filter_logic_operator = OR

                # if filter_str == CUSTOM_FILTER:
                #     filter_str = RESTAURANT_ID
                #     filter_list = self._get_custom_filter_restaurant_ids(filter_list)
            else:
                logging.warning('Unexpected supported filter:')
                continue
            # if filter_list is None:
            # TODO: figure out why the list is empty sometimes (should just be None)
            if filter_list is None or filter_list == []:
                continue
            filter_str_list_and_operator_list.append((filter_str, filter_list, filter_logic_operator))

        return filter_str_list_and_operator_list

    def _build_query(self, filter_str_list_and_operator_list):
        subquery_list = []
        for filter_str, filter_list, filter_logic_operator in filter_str_list_and_operator_list:
            subquery = self._build_subquery(filter_str, filter_list, filter_logic_operator)
            if subquery != {}:
                subquery_list.append(subquery)

        # Create query out of subqueries
        n_subqueries = len(subquery_list)
        if n_subqueries == 0:  # No filters, so don't run a DB query or print any message
            return
            # query = {}
        elif n_subqueries == 1:  # Use the single subquery as the whole query
            query = subquery_list[0]
        else:  # Take an AND of all subqueries
            query = {'$and': subquery_list}

        return query

    def _build_subquery(self, filter_str, filter_list, filter_logic_operator):

        # TODO: validate_filter
        # validate_filter(filter_str, filter_list, filter_logic_operator)

        if filter_str == CUSTOM_FILTER:
            filter_str = RESTAURANT_ID
            filter_list = self._get_custom_filter_restaurant_ids(filter_list)

        n_filter_values = len(filter_list)

        # Map the filter to MongoDB query
        if filter_str in YELP_CATEGORY_ATTRIBUTES:
            if filter_logic_operator == NOT:
                inner_dict = {'$nin': filter_list}
            elif filter_logic_operator == AND:
                inner_dict = {'$all': filter_list}
            elif filter_logic_operator == OR:
                inner_dict = {'$in': filter_list}
            else:
                logging.warning(f'Invalid logical operator for {filter_str}: {filter_logic_operator}')
                inner_dict = {'$in': filter_list}  # Just use the OR logic
            subquery = {'categories': inner_dict}

        elif filter_str == CITY or filter_str == ZIP_CODE or filter_str == RESTAURANT_ID:
            if n_filter_values == 1:
                subquery = {filter_str: filter_list[0]}
            else:  # n_filter_values > 1
                subquery = {
                    '$or': [{filter_str: filter_value} for filter_value in filter_list]
                }
            if filter_str == RESTAURANT_ID:
                print('RESTAURANT_ID subquery:', subquery)

        elif filter_str == PRICE:
            price_list = [int(price) for price in filter_list]
            if filter_logic_operator == OR or filter_logic_operator == AND:  # Just ignores AND and maps to OR
                if n_filter_values == 1:
                    subquery = {PRICE: price_list[0]}
                else:  # n_filter_values > 1
                    subquery = {
                        '$or': [{PRICE: price} for price in price_list]
                    }
            # TODO: consider removing support for NOT for price
            elif filter_logic_operator == NOT:
                price_list.append(-1)
                subquery = {
                    PRICE: {
                        '$nin': price_list
                    }
                }
            else:
                logging.warning(f'Invalid logical operator for {filter_str}: {filter_logic_operator}')
                subquery = {}

        elif filter_str in NON_AMENITY_ATTRIBUTES:
            filter_key = f'{ATTRIBUTES}.{filter_str}'
            if filter_logic_operator == NOT:
                logging.warning(f'Invalid "NOT" operator was given for a non-cuisine filter: "{filter_str}"')
                subquery = {}
            elif filter_logic_operator == AND or filter_logic_operator == OR:
                if n_filter_values == 1:
                    subquery = {f'{filter_key}.{filter_list[0]}': True}
                else:  # n_filter_values > 1
                    conjunction = {
                        AND: '$and',
                        OR: '$or'
                    }[filter_logic_operator]
                    subquery = {
                        conjunction: [{f'{filter_key}.{filter_value}': True} for filter_value in filter_list]
                    }
            else:
                logging.warning(f'Invalid logical operator for {filter_str}: {filter_logic_operator}')
                subquery = {}

        else:
            logging.warning(f'Database query code for supported filter "{filter_str}" is not yet written.')
            subquery = {}

        return subquery

    @staticmethod
    def _query_db(query, max_n_restaurants=MAX_N_RESTAURANTS):
        print('Query:')
        json_serialized_query = json_util.dumps(query)
        print(json.dumps(json_serialized_query))
        print('Pretty query:')
        print(json.dumps(json_serialized_query, sort_keys=False, indent=4))

        # Query the database
        client = MongoClient(MONGODB_CREDENTIAL_URL)
        result = client['yelp']['restaurants'].find(
            filter=query
        ).sort('rating', pymongo.DESCENDING)[:max_n_restaurants]
        result_count = min(MAX_N_RESTAURANTS, result.count())

        return result, result_count

    @staticmethod
    def _utter_matches(dispatcher, result, n_restaurants):
        restaurant_strs = [f'Here are the top {n_restaurants} rated restaurants that match your criteria:']
        for i, item in enumerate(result):
            website = item['website']
            if website == '':
                website = item['url']
            if not website.startswith('http'):
                # TODO: detect if the site supports https and use that if it does
                website = 'http://' + website

            rating = item['rating']
            stars = '★' * floor(item['rating'])
            if rating % 1 == 0.5:
                stars = stars + ' + 1/2'

            restaurant_strs.append(f"{i + 1}. [{item['name']}]({website}) ({stars})")

        message = '\n\t'.join(restaurant_strs)
        dispatcher.utter_message(message)
        return message

    def _remove_filters_and_utter_matches(self, dispatcher, filter_str_list_and_operator_list):
        no_matches_message = random.choice([
            "Ack, no restaurants that match those filters.",
            "Ahh! Too many filters. There aren't any matching restaurants.",
            "No matching restaurants, mate.",
        ])
        # Iterate over all possible removal filters, starting with no removal filters
        for n_filters_to_remove in range(1, len(filter_str_list_and_operator_list) - 1):
            removal_combinations = list(combinations(reversed(filter_str_list_and_operator_list), n_filters_to_remove))
            print('removal_combinations:', removal_combinations)
            for candidate_removal_filters in removal_combinations:
                print('candidate_removal_filters:', candidate_removal_filters)
                candidate_removal_filter_strs = [filter_str for filter_str, _, _ in candidate_removal_filters]
                print('candidate_removal_filter_strs:', candidate_removal_filter_strs)
                candidate_filter_tuple_list = [filter_tuple for filter_tuple in filter_str_list_and_operator_list
                                               if filter_tuple[0] not in set(candidate_removal_filter_strs)]
                print('candidate_filter_tuple_list:', candidate_filter_tuple_list)
                query = self._build_query(candidate_filter_tuple_list)
                result, n_matches = self._query_db(query)

                if n_matches > 0:
                    removed_filter_classes = [filter_class
                                              for _, filter_classes, _ in candidate_removal_filters
                                              for filter_class in filter_classes]
                    filter_removal_message = f"I've removed the following filters for you so you get some " \
                                             f"matching restaurants: {removed_filter_classes}."
                    dispatcher.utter_message(no_matches_message + ' ' + filter_removal_message)
                    self._utter_matches(dispatcher, result, n_matches)
                    return get_filter_removal_events(candidate_removal_filter_strs)
                else:  # No matches
                    continue

    @staticmethod
    def _send_no_match_meme_message(dispatcher):
        # Choose a random message and meme and send them to the user

        # Potential phrases and meme images
        no_match_phrases = [
            "Ack, no restaurants that match those filters.",
            "Ahh! Too many filters. There aren't any matching restaurants.",
            "No matching restaurants, mate.",
        ]
        meme_images = [
            # Too picky Morpheus meme
            'https://memegenerator.net/img/instances/39296172/what-if-i-told-you-that-you-are-too-picky.jpg',

            # Funny faces from having too much information
            'https://i.imgflip.com/gfos9.jpg',  # woman
            'https://i.imgflip.com/lh1o4.jpg',  # cat
            'https://media.makeameme.org/created/information-you-give.jpg',  # Yoda
        ]
        tinder_messages_memes = [
            ("No matches. Good thing this isn't Tinder.", 'https://memegenerator.net/img/instances/50278365.jpg'),
            ("No matches. Let's get you some so you don't have to be a surprised pikachu.",
             'https://i.redd.it/uuuwl29xtzw11.jpg'),
            ("No restaurant matches. Can't have bad food if you get no matches. Though, you get no matches...",
             'https://memegenerator.net/img/instances/75640312.jpg'),
        ]
        remove_filters_phrases = [
            "Try removing filters.",
            "You'll have to remove some filters.",
            "Remove some filters to get matches.",
        ]

        # Choose whether to send a Tinder message or a regular message
        p_tinder_meme = 0.2
        if random.random() < p_tinder_meme:
            no_match, image = random.choice(tinder_messages_memes)

        else:
            no_match = random.choice(no_match_phrases)
            image = random.choice(meme_images)

        print('no_match:', no_match)
        print('image:', image)
        # Choose phrase to add that tells the user to remove filters
        message = no_match + ' ' + random.choice(remove_filters_phrases)
        print('message:', message)

        dispatcher.utter_message(message, image=image)
        return message
