import logging
from typing import Text, Dict, Any, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
# from negation.pycontext_nlp import PyConTextNLPNegator

from const import (RASA_ENTITIES_LIST, RASA_ENTITY_TYPE, RASA_ENTITY_VALUE, RASA_ENTITY_ROLE,
                   RASA_ENTITY_RAW, RASA_ENTITY_CLASS, RASA_ENTITY_OPERATOR,
                   LOGICAL_OPERATORS, AND, OR, NOT, DEFAULT_OPERATOR,
                   CLASS_FILTERS, SPACY_ENTITIES, SPACY_ENTITY_MAPPING,
                   CITY, SUPPORTED_CITIES, SUPPORTED_AREAS,
                   RAW_FILTERS, CUSTOM_FILTER)


class ActionProcessPreferences(Action):

    def name(self) -> Text:
        return "action_process_preferences"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Initialize what the slots will be updated to
        update_slots = self._initialize_update_slots(tracker)

        # Parse through all entities in the last message to update slots
        for entity in tracker.latest_message[RASA_ENTITIES_LIST]:
            self._update_entity_slot(entity, update_slots)
            
        # Set logical operators
        self._set_logical_operators(update_slots)

        # Remove any slots such as unsupported cities
        self._cleanup_update_slots(update_slots, dispatcher)

        # Create slot update events from update_slots
        return self._get_slot_update_events(update_slots)

    def _initialize_update_slots(self, tracker):
        update_slots = {}
        for entity in tracker.latest_message[RASA_ENTITIES_LIST]:
            entity_type = self._get_entity_type(entity)
            if entity_type is None:
                continue
            elif entity_type == CUSTOM_FILTER:  # TODO: generalize to RAW_LIST_FILTERS when there are more like this
                prev_custom_filters = tracker.get_slot(CUSTOM_FILTER)
                if prev_custom_filters is None:
                    update_slots[entity_type] = []
                else:
                    update_slots[entity_type] = prev_custom_filters
            elif entity_type in RAW_FILTERS:
                update_slots[entity_type] = []
            elif entity_type in CLASS_FILTERS:
                update_slots[entity_type] = {
                    RASA_ENTITY_RAW: [], RASA_ENTITY_CLASS: [], RASA_ENTITY_OPERATOR: []
                }
            else:
                logging.warning('Unsupported slot init: {}'.format(entity_type))
                continue
        return update_slots

    @staticmethod
    def _get_entity_type(entity):
        entity_type = entity[RASA_ENTITY_TYPE]
        print('entity_type:', entity_type)

        # Map Spacy entities to ones in corresponding slots
        if entity_type in RAW_FILTERS or entity_type in CLASS_FILTERS:
            print('raw or class')
            pass
        elif entity_type in SPACY_ENTITIES:
            print('mapping!')
            entity_type = SPACY_ENTITY_MAPPING[entity_type]
            print('entity_type:', entity_type)
        else:
            logging.warning('Unsupported slot: {}'.format(entity_type))
            return None

        return entity_type

    def _update_entity_slot(self, entity, update_slots):
        entity_type = self._get_entity_type(entity)
        if entity_type is None:
            return

        # Get the raw text that was extracted for that entity
        raw_entity = entity[RASA_ENTITY_VALUE]

        # Handle the case where the raw entity should just be added to a list
        if entity_type in RAW_FILTERS:
            update_slots[entity_type].append(raw_entity)
        elif entity_type in CLASS_FILTERS:
            # If there is a role, set the role as the class; otherwise, set the class to the entity's raw text
            if RASA_ENTITY_ROLE in entity.keys():
                entity_class = entity[RASA_ENTITY_ROLE]
            else:
                if entity_type == CITY:
                    entity_class = raw_entity.title()
                else:
                    entity_class = raw_entity

            # Check if the entity is a logical operator or not
            potential_operator = entity_class.upper()
            if potential_operator in LOGICAL_OPERATORS:
                # Append the logical operator to the logical operators list
                update_slots[entity_type][RASA_ENTITY_OPERATOR].append(potential_operator)
            else:
                # Append the entity raw text and class to the associated lists
                update_slots[entity_type][RASA_ENTITY_RAW].append(raw_entity)
                update_slots[entity_type][RASA_ENTITY_CLASS].append(entity_class)

    @staticmethod
    def _set_logical_operators(update_slots):
        # Set the logical operator updated slots
        for entity_type in update_slots.keys():
            if entity_type in CLASS_FILTERS:
                entity_logical_operators = set(update_slots[entity_type][RASA_ENTITY_OPERATOR])
                contains_and = AND in entity_logical_operators
                contains_or = OR in entity_logical_operators
                if NOT in entity_logical_operators:
                    update_slots[entity_type][RASA_ENTITY_OPERATOR] = NOT
                elif (contains_and and contains_or) or len(entity_logical_operators) == 0:
                    update_slots[entity_type][RASA_ENTITY_OPERATOR] = DEFAULT_OPERATOR[entity_type]
                elif contains_and:
                    update_slots[entity_type][RASA_ENTITY_OPERATOR] = AND
                elif contains_or:
                    update_slots[entity_type][RASA_ENTITY_OPERATOR] = OR
                else:
                    logging.warning('Unexpected logical operator case')

    @staticmethod
    def _cleanup_update_slots(update_slots, dispatcher):
        # TODO: generalize this to ZIP_CODE
        # Validate cities, remove any that aren't valid, and alert the user
        if CITY in update_slots.keys():
            raw_cities = update_slots[CITY][RASA_ENTITY_RAW]
            city_classes = update_slots[CITY][RASA_ENTITY_CLASS]

            # Get unsupported cities
            unsupported_cities = []
            unsupported_city_classes = []
            for raw_city, city_class in zip(raw_cities,
                                            city_classes):  # raw_city and city_class should be the same for now
                if city_class not in SUPPORTED_CITIES:
                    unsupported_cities.append(raw_city)
                    unsupported_city_classes.append(city_class)

            # Remove unsupported cities from city slots
            n_cities = len(raw_cities)
            n_unsupported_cities = len(unsupported_cities)
            n_supported_cities = n_cities - n_unsupported_cities
            if n_supported_cities == 0:
                update_slots[CITY][RASA_ENTITY_RAW] = None
                update_slots[CITY][RASA_ENTITY_CLASS] = None
            else:
                update_slots[CITY][RASA_ENTITY_RAW] = [city for city in raw_cities if city not in unsupported_cities]
                update_slots[CITY][RASA_ENTITY_CLASS] = [city for city in city_classes if
                                                          city not in unsupported_city_classes]

            # Message the user about unsupported cities, if any
            if n_unsupported_cities == 0:
                message = None
            elif n_unsupported_cities == 1:
                unsupported_city = unsupported_cities[0]
                if n_cities == 1:
                    message = f'Eek! We do not yet support the location "{unsupported_city}".'
                elif n_cities > 1:
                    message = f'We do not yet support the location "{unsupported_city}", ' \
                              f'but we support the other location{"s" if n_unsupported_cities > 1 else ""} you gave.'
                else:
                    logging.warning(f'Unexpected n_cities: {n_cities}')
                    return []
            else:  # n_unsupported_cities > 1
                if n_cities > n_unsupported_cities:
                    message = f'We do not yet support the locations {unsupported_cities}, ' \
                              f'but we support the other location{"s" if n_unsupported_cities > 1 else ""} you gave.'
                else:  # n_cities == n_unsupported_cities
                    message = f'Eek! We do not yet support the locations {unsupported_cities}.'

            if message is not None:
                supported_areas_message = f' Please choose locations in our currently supported areas: {SUPPORTED_AREAS}.'
                dispatcher.utter_message(message + supported_areas_message)

    @staticmethod
    def _get_slot_update_events(update_slots):
        slot_update_events = []
        for entity_type in update_slots.keys():
            if entity_type in RAW_FILTERS:
                slot_update_events.append(SlotSet(entity_type, update_slots[entity_type]))
            elif entity_type in CLASS_FILTERS:
                slot_update_events.append(SlotSet(entity_type + RASA_ENTITY_RAW,
                                                  update_slots[entity_type][RASA_ENTITY_RAW]))
                slot_update_events.append(SlotSet(entity_type + RASA_ENTITY_CLASS,
                                                  update_slots[entity_type][RASA_ENTITY_CLASS]))
                slot_update_events.append(SlotSet(entity_type + RASA_ENTITY_OPERATOR,
                                                  update_slots[entity_type][RASA_ENTITY_OPERATOR]))
        return slot_update_events



    # def _process_entity_negations(self, message, entities):
    #     negator = PyConTextNLPNegator(message)
    #     entity_negations = negator.are_negated(entities)
    #     for entity, negated in entity_negations.items():
    #         if negated:
    #             # TODO: negate entity
    #             pass
    #
    #     return []
