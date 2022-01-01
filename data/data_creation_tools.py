import re
from typing import Callable, List

import inflect

from const import (GIVE_PREFERENCES_INTENT, RASA_ENTITY_TYPE, RASA_ENTITY_ROLE,
                   CUISINE, YELP_CUISINES,
                   RESTAURANT_TYPE, YELP_RESTAURANT_TYPES,
                   RESTAURANT_FOOD_TYPE, YELP_RESTAURANT_FOOD_TYPES,
                   PRICE)


def print_intent_preamble(intent):
    print('- intent: ' + intent)
    print('  examples: |')


class DataCreator:

    def __init__(self, entity_type: str, intent: str = None, raw_data=None):
        self._entity_type = entity_type
        self._intent = intent
        self._data = None

        if raw_data is not None:
            self.load_raw_data(raw_data=raw_data)

    def load_raw_data(self, raw_data, delimiter: str = '\n'):
        if isinstance(raw_data, str):
            self._data = raw_data.split(delimiter)
        elif isinstance(raw_data, list):
            self._data = raw_data
        else:
            raise ValueError(f'Invalid "data" type: {type(data)}')

    def print_data(self, raw_text_mapper: Callable = None, alias_text_mapper: Callable = None,
                   alias_delimiters: List[str] = ['/', '&'], lower: bool = False):
        if self._intent is not None:
            print_intent_preamble(self._intent)

        n_examples = 0
        for datum in self._data:
            # If raw_text_mapper function is provided, apply it to the data
            if raw_text_mapper is None:
                datum_text = datum  # Identity mapping
            else:
                datum_text = raw_text_mapper(datum)
                # Don't print any data that maps to False
                if not datum_text:
                    continue

            # Split on alias_delimiters to get aliases
            datum_aliases = [datum_text]
            for alias_delimiter in alias_delimiters:
                if alias_delimiter in datum_text:
                    datum_aliases.extend([alias.strip() for alias in datum.split(alias_delimiter)])

            # Loop over aliases
            for datum_alias in datum_aliases:
                # If alias_text_mapper function is provided, apply it to the alias
                if alias_text_mapper is None:
                    pass
                else:
                    datum_alias = alias_text_mapper(datum_alias)
                    # Don't print any data that maps to False
                    if not datum_alias:
                        continue

                # Optionally make alias lowercase
                if lower:
                    datum_alias = datum_alias.lower()
                print(f'    - [{datum_alias}]{{"{RASA_ENTITY_TYPE}": "{self._entity_type}", "{RASA_ENTITY_ROLE}": "{datum}"}}')
                n_examples += 1

        print('\nN examples:', n_examples)


### Pure data generation ###

def cuisine_mapper(cuisine):
    if '(' in cuisine:
        if cuisine == 'American (New)':
            return 'New American'
        elif cuisine == 'American (Traditional)':
            return 'Traditional American'
        else:
            raise Exception(f'Unexpected cuisine: {cuisine}')
    else:
        return cuisine


def plural_to_singular_inclusive(phrase):
    singular = inflect.engine().singular_noun(phrase)
    return singular if singular else phrase


def plural_to_singular_exclusive(phrase):
    return inflect.engine().singular_noun(phrase)


cuisine_data_creator = DataCreator(entity_type=CUISINE, intent=GIVE_PREFERENCES_INTENT, raw_data=YELP_CUISINES)
cuisine_data_creator.print_data(cuisine_mapper, lower=False)
cuisine_data_creator.print_data(cuisine_mapper, lower=True)

# TODO: add custom mapping for "Pop-Up Restaurants"
restaurant_type_data_creator = DataCreator(entity_type=RESTAURANT_TYPE, intent=GIVE_PREFERENCES_INTENT, raw_data=YELP_RESTAURANT_TYPES)
restaurant_type_data_creator.print_data(lower=False)
restaurant_type_data_creator.print_data(alias_text_mapper=plural_to_singular_inclusive, lower=True)

restaurant_food_type_data_creator = DataCreator(entity_type=RESTAURANT_FOOD_TYPE, intent=GIVE_PREFERENCES_INTENT, raw_data=YELP_RESTAURANT_FOOD_TYPES)
restaurant_food_type_data_creator.print_data(lower=False)
restaurant_food_type_data_creator.print_data(lower=True)




# # Generate Yelp cuisine data
# print_intent_preamble(GIVE_PREFERENCES_INTENT)
# for cuisine in YELP_CUISINES:
#     cuisine_str = cuisine
#     if '(' in cuisine:
#         if cuisine == 'American (New)':
#             cuisine_str = 'New American'
#         elif cuisine == 'American (Traditional)':
#             cuisine_str = 'Traditional American'
#         else:
#             raise Exception(f'Unexpected cuisine: {cuisine}')
#     cuisine_aliases = [cuisine_str]
#     if '/' in cuisine:
#         cuisine_aliases.extend(cuisine.split('/'))
#     # print(f'    - [{cuisine}]{{"{RASA_ENTITY_TYPE}": "{CUISINE}", "{RASA_ENTITY_ROLE}": "{cuisine}"}}')
#     for cuisine_alias in cuisine_aliases:
#         print(f'    - [{cuisine_alias}]{{"{RASA_ENTITY_TYPE}": "{CUISINE}", "{RASA_ENTITY_ROLE}": "{cuisine}"}}')
#
# # Generate lowercase Yelp cuisine data
# print_intent_preamble(GIVE_PREFERENCES_INTENT)
# for cuisine in YELP_CUISINES:
#     cuisine_str = cuisine
#     if '(' in cuisine:
#         if cuisine == 'American (New)':
#             cuisine_str = 'New American'
#         elif cuisine == 'American (Traditional)':
#             cuisine_str = 'Traditional American'
#         else:
#             raise Exception(f'Unexpected cuisine: {cuisine}')
#     cuisine_aliases = [cuisine_str]
#     if '/' in cuisine:
#         cuisine_aliases.extend(cuisine.split('/'))
#     # print(f'    - [{cuisine}]{{"{RASA_ENTITY_TYPE}": "{CUISINE}", "{RASA_ENTITY_ROLE}": "{cuisine}"}}')
#     for cuisine_alias in cuisine_aliases:
#         print(f'    - [{cuisine_alias.lower()}]{{"{RASA_ENTITY_TYPE}": "{CUISINE}", "{RASA_ENTITY_ROLE}": "{cuisine}"}}')

############################



### Editing and generating data ###

# Add empty roles to price data
price_lines = """- [cheap](price)
- [expensive](price)
- [very cheap](price)
- [inexpensive](price)
- [low cost](price)
- [low priced](price)
- [low-cost](price)
- [reasonable](price)
- [affordable](price)
- [moderately priced](price)
- [reasonably priced](price)
- [not too bad](price)
- [not too expensive](price)
- [not too pricey](price)
- [reasonable deal](price)
- [reasonable price](price)
- [budget](price)
- [costly](price)
- [overpriced](price)
- [extravagant](price)
- [highly priced](price)
- [pricey](price)
- [wallet-draining](price)
- [high-priced](price)
- [high-end](price)
- [steep](price)""".split('\n')
print_intent_preamble(GIVE_PREFERENCES_INTENT)
for price_line in price_lines:
    price_example = re.findall(f'- \[(.+)\]\({PRICE}\)', price_line)[0]
    # print(matched_list)
    assert isinstance(price_example, str)
    print(f'    - [{price_example}]{{"{RASA_ENTITY_TYPE}": "{PRICE}", "{RASA_ENTITY_ROLE}": ""}}')

###################################
