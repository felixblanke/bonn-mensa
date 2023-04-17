import argparse
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set

import requests
from colorama import Fore, Style
from colorama import init as colorama_init

meat_allergens: Dict[str, Set[str]] = {
    "de": set(
        [
            "Krebstiere (41)",
            "Fisch (43)",
            "Weichtiere (53)",
            "Kalbfleisch (K)",
            "Schweinefleisch (S)",
            "Rindfleisch (R)",
            "Lammfleisch (L)",
            "Geflügel (G)",
            "Fisch (F)",
        ]
    ),
    "en": set(
        [
            "crustaceans (41)",
            "fish (43)",
            "mollusks (53)",
            "veal (K)",
            "pork (S)",
            "beef (R)",
            "lamb (L)",
            "poultry (G)",
            "fish (F)",
        ]
    ),

}

ovo_lacto_allergens = {
    "de": set(
        [
            "Eier (42)",
            "Milch (46)",
        ]
    ),
    "en": set(
        [
            "eggs (42)",
            "milk (46)"
        ]
    )
}

other_allergens: Dict[str, Set[str]] = {
    "de": set(),
    "en": set(),
}

canteen_id_dict = {
    "SanktAugustin": "1",
    "CAMPO": "2",
    "Hofgarten": "3",
    "FoodtruckRheinbach": "5",
    "VenusbergBistro": "6",
    "CasinoZEF/ZEI": "8",
    "Foodtruck": "19",
}

language_id_dict = {
    "de": "0",
    "en": "1",
}

content_strings = {
    "NEW_INFOS_ALLERGENS": {
        "de": "Allergene",
        "en": "Allergens",
    },
    "NEW_INFOS_ADDITIVES": {
        "de": "Zusatzstoffe",
        "en": "Additives",
    },
    "PRICE_CATEGORY_STUDENT": {
        "de": "Stud.",
        "en": "Student",
    },
    "PRICE_CATEGORY_STAFF": {
        "de": "Bed.",
        "en": "Staff",
    },
    "PRICE_CATEGORY_GUEST": {
        "de": "Gast",
        "en": "Guest",
    },
}

output_strs = {
    "MD_TABLE_COL_CAT": {
        "de": "Kategorie",
        "en": "Category",
    },
    "MD_TABLE_COL_MEAL": {
        "de": "Gericht",
        "en": "Meal",
    },
    "MD_TABLE_COL_PRICE": {
        "de": "Preis",
        "en": "Price",
    },
    "MD_TABLE_COL_SOME_ALLERGENS": {
        "de": "Allergene (Auswahl)",
        "en": "Allergens (Selection)",
    },
    "MD_TABLE_COL_ALLERGENS": {
        "de": "Allergene",
        "en": "Allergens",
    },
    "MD_TABLE_COL_ADDITIVES": {
        "de": "Zusatzstoffe",
        "en": "Additives",
    },
}


class Meal:
    def __init__(self, title: str) -> None:
        self.title = title
        self.allergens: List[str] = []
        self.additives: List[str] = []
        self.student_price: Optional[int] = None
        self.staff_price: Optional[int] = None
        self.guest_price: Optional[int] = None

    def add_allergen(self, allergen: str) -> None:
        self.allergens.append(allergen)

    def add_additive(self, additive: str) -> None:
        self.additives.append(additive)


class Category:
    def __init__(self, title: str) -> None:
        self.title = title
        self.meals: List[Meal] = []

    def add_meal(self, meal: Meal) -> None:
        self.meals.append(meal)


class SimpleMensaResponseParser(HTMLParser):
    def __init__(self, lang: str, verbose: bool = False):
        super().__init__()
        self.curr_category: Optional[Category] = None
        self.curr_meal: Optional[Meal] = None

        self.last_tag: Optional[str] = None
        self.last_nonignored_tag: Optional[str] = None
        self.categories: List[Category] = []
        self.mode = "INIT"

        self.lang = lang
        self.verbose = verbose

    def start_new_category(self):
        if self.curr_category:
            if self.curr_meal:
                self.curr_category.add_meal(self.curr_meal)
                self.curr_meal = None
            self.categories.append(self.curr_category)
            self.curr_category = None

        self.mode = "NEW_CAT"

    def start_new_meal(self):
        if not self.curr_category:
            self.curr_category = Category("DUMMY-Name")

        if self.curr_meal:
            self.curr_category.add_meal(self.curr_meal)
            self.curr_meal = None

        self.mode = "NEW_MEAL"

    def handle_starttag(self, tag, attrs):
        # skip non-empty attributes
        if attrs or tag not in ["h2", "h5", "strong", "p", "th", "td", "br"]:
            self.mode = "IGNORE"
            return

        self.last_nonignored_tag = tag
        if tag == "h2":
            self.start_new_category()
        elif tag == "h5":
            self.start_new_meal()
        elif tag == "strong":
            self.mode = "NEW_INFOS"
        elif tag == "p":
            if not self.curr_meal and not self.curr_category:
                self.mode = "INFO"
        elif tag == "th":
            self.mode = "NEW_PRICE_CAT"
        elif tag == "td":
            pass

    def parse_price(self, price: str) -> int:
        return int("".join(digit for digit in price if digit.isdigit()))

    def handle_data(self, data):
        if self.mode == "IGNORE" or not data.strip():
            return
        if self.mode in ["INIT", "INFO"]:
            print(data)
            return
        data = data.strip()
        if self.mode == "NEW_CAT":
            self.curr_category = Category(data)
            if self.verbose:
                print(f"Creating new category {data}")
        elif self.mode == "NEW_MEAL":
            self.curr_meal = Meal(data)
            if self.verbose:
                print(f"\tCreating new meal {data}")
        elif self.mode == "NEW_INFOS":
            if data == content_strings["NEW_INFOS_ALLERGENS"][self.lang]:
                self.mode = "NEW_ALLERGENS"
            elif data == content_strings["NEW_INFOS_ADDITIVES"][self.lang]:
                self.mode = "NEW_ADDITIVES"
            else:
                raise NotImplementedError(f"Mode NEW_INFOS with data {data}")
        elif self.mode == "NEW_ALLERGENS":
            if self.verbose:
                print(f"\t\tAdding new allergen: {data}")
            self.curr_meal.add_allergen(data)
        elif self.mode == "NEW_ADDITIVES":
            if self.verbose:
                print(f"\t\tAdding new additive: {data}")
            self.curr_meal.add_additive(data)
        elif self.mode == "NEW_PRICE_CAT":
            if data == content_strings["PRICE_CATEGORY_STUDENT"][self.lang]:
                self.mode = "NEW_PRICE_STUDENT"
            elif data == content_strings["PRICE_CATEGORY_STAFF"][self.lang]:
                self.mode = "NEW_PRICE_STAFF"
            elif data == content_strings["PRICE_CATEGORY_GUEST"][self.lang]:
                self.mode = "NEW_PRICE_GUEST"
            else:
                raise NotImplementedError(f"Mode NEW_PRICE_CAT with data {data}")
        elif self.mode == "NEW_PRICE_STUDENT":
            assert self.last_nonignored_tag == "td"
            self.curr_meal.student_price = self.parse_price(data)
        elif self.mode == "NEW_PRICE_STAFF":
            assert self.last_nonignored_tag == "td"
            self.curr_meal.staff_price = self.parse_price(data)
        elif self.mode == "NEW_PRICE_GUEST":
            assert self.last_nonignored_tag == "td"
            self.curr_meal.guest_price = self.parse_price(data)
        else:
            raise NotImplementedError(f"{self.last_nonignored_tag} with data {data}")

    def close(self):
        super().close()
        self.start_new_category()


def query_mensa(
    date: Optional[str],
    canteen: str,
    filtered_categories: List[str],
    language: str,
    filter_mode: Optional[str] = None,
    show_all_allergens: bool = False,
    show_additives: bool = False,
    url: str = "https://www.studierendenwerk-bonn.de/index.php?ajax=meals",
    verbose: bool = False,
    colors: bool = True,
    markdown_output: bool = False,
) -> None:
    if date is None:
        from datetime import datetime

        date = datetime.today().strftime("%Y-%m-%d")

    if colors:
        QUERY_COLOR = Fore.MAGENTA
        CATEGORY_COLOR = Fore.GREEN
        MEAL_COLOR = Fore.BLUE
        PRICE_COLOR = Fore.CYAN
        ALLERGEN_COLOR = Fore.RED
        ADDITIVE_COLOR = Fore.YELLOW
        WARN_COLOR = Fore.RED
        RESET_COLOR = Style.RESET_ALL
    else:
        QUERY_COLOR = ""
        CATEGORY_COLOR = ""
        MEAL_COLOR = ""
        PRICE_COLOR = ""
        ALLERGEN_COLOR = ""
        ADDITIVE_COLOR = ""
        WARN_COLOR = ""
        RESET_COLOR = ""

    filter_str = f" [{filter_mode}]" if filter_mode else ""
    if markdown_output:
        print(f"### Mensa {canteen} – {date}{filter_str} [{language}]\n")
    else:
        print(
            f"{QUERY_COLOR}Mensa {canteen} – {date}{filter_str} [{language}]{RESET_COLOR}"
        )

    if verbose:
        print(
            f"Querying for {date=}, {canteen=}, {filtered_categories=}, {filter_mode=}, {url=}"
        )

    r = requests.post(
        url,
        data={
            "date": date,
            "canteen": canteen_id_dict[canteen],
            "L": language_id_dict[language],
        },
    )
    parser = SimpleMensaResponseParser(lang=language, verbose=verbose)
    parser.feed(r.text)
    parser.close()

    if not parser.categories:
        print(
            f"{WARN_COLOR}Query failed. Please check https://www.studierendenwerk-bonn.de if the mensa is open today.{RESET_COLOR}"
        )
        return
    print()

    queried_categories = [
        cat for cat in parser.categories if cat.title not in filtered_categories
    ]
    if not queried_categories:
        return

    interesting_allergens = meat_allergens[language] | ovo_lacto_allergens[language] | other_allergens[language]

    if filter_mode is None:
        remove_allergens = set()
    elif filter_mode == "vegetarian":
        remove_allergens = meat_allergens[language]
    elif filter_mode == "vegan":
        remove_allergens = meat_allergens[language] | ovo_lacto_allergens[language]
    else:
        raise NotImplementedError(filter_mode)

    maxlen_catname = max(len(cat.title) for cat in queried_categories)
    if markdown_output:
        print(f"| {output_strs['MD_TABLE_COL_CAT'][language]}", end="")
        print(f"| {output_strs['MD_TABLE_COL_MEAL'][language]}", end="")
        print(f"| {output_strs['MD_TABLE_COL_PRICE'][language]}", end="")
        if show_all_allergens:
            print(f"| {output_strs['MD_TABLE_COL_ALLERGENS'][language]}", end="")
        else:
            print(f"| {output_strs['MD_TABLE_COL_SOME_ALLERGENS'][language]}", end="")
        if show_additives:
            print(f"| {output_strs['MD_TABLE_COL_ADDITIVES'][language]}", end="")
        print("|")
        print(f"| :-- | :-- | --: | :-- | ", end="")
        if show_additives:
            print(":-- |")
        else:
            print()

    for cat in queried_categories:
        filtered_meals = [
            meal for meal in cat.meals if not set(meal.allergens) & remove_allergens
        ]

        if not filtered_meals:
            continue

        if markdown_output:
            for meal_idx, meal in enumerate(filtered_meals):
                if meal_idx:
                    print(f"| |", end="")
                else:
                    print(f"| {cat.title} |", end="")

                print(f" {meal.title} | {meal.student_price/100:.2f}€ |", end="")

                if show_all_allergens:
                    allergen_str = ", ".join(meal.allergens)
                else:
                    allergen_str = ", ".join(
                        al for al in meal.allergens if al in interesting_allergens
                    )
                print(f" {allergen_str} |", end="")

                if show_additives:
                    additives_str = ", ".join(meal.additives)
                    print(f" {additives_str} |", end="")

                print("")
        else:
            cat_str = cat.title.ljust(maxlen_catname + 1)
            print(f"{CATEGORY_COLOR}{cat_str}{RESET_COLOR}", end="")

            for meal_idx, meal in enumerate(filtered_meals):
                # do not indent first line
                if meal_idx:
                    print(" " * (maxlen_catname + 1), end="")
                print(
                    f"{MEAL_COLOR}{meal.title} {PRICE_COLOR}({meal.student_price/100:.2f}€)",
                    end="",
                )
                if meal.allergens and (
                    show_all_allergens or set(meal.allergens) & interesting_allergens
                ):
                    if show_all_allergens:
                        allergen_str = ", ".join(meal.allergens)
                    else:
                        allergen_str = ", ".join(
                            al for al in meal.allergens if al in interesting_allergens
                        )
                    print(f" {ALLERGEN_COLOR}[{allergen_str}]", end="")

                if show_additives and meal.additives:
                    additives_str = ", ".join(meal.additives)
                    print(f" {ADDITIVE_COLOR}[{additives_str}]", end="")

                print(f"{RESET_COLOR}")


def get_parser():
    parser = argparse.ArgumentParser("mensa")
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument(
        "--vegan", action="store_true", help="Only show vegan options"
    )
    filter_group.add_argument(
        "--vegetarian", action="store_true", help="Only show vegetarian options"
    )
    parser.add_argument(
        "--mensa",
        choices=canteen_id_dict.keys(),
        type=str,
        default="CAMPO",
        help="The canteen to query. Defaults to CAMPO.",
    )
    parser.add_argument(
        "--filter-categories",
        nargs="*",
        metavar="CATEGORY",
        default=["Buffet", "Dessert"],
        help="Meal categories to hide. Defaults to ['Buffet', 'Dessert'].",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="The date to query for in YYYY-MM-DD format. Defaults to today.",
    )

    parser.add_argument(
        "--lang",
        choices=["de", "en"],
        default="de",
        help="The language of the meal plan to query. Defaults to German.",
    )

    parser.add_argument(
        "--show-all-allergens",
        action="store_true",
        help="Show all allergens. By default, only allergens relevant to vegans (e.g. milk or fish) are shown.",
    )

    parser.add_argument(
        "--show-additives",
        action="store_true",
        help="Show additives.",
    )

    parser.add_argument(
        "--no-colors",
        action="store_true",
        help="Do not use any ANSI colors in the output.",
    )

    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Output in markdown table format.",
    )

    return parser


def run_cmd(args):
    if args.vegan:
        filter_mode: Optional[str] = "vegan"
    elif args.vegetarian:
        filter_mode = "vegetarian"
    else:
        filter_mode = None

    query_mensa(
        date=args.date,
        canteen=args.mensa,
        language=args.lang,
        filtered_categories=args.filter_categories,
        filter_mode=filter_mode,
        show_all_allergens=args.show_all_allergens,
        show_additives=args.show_additives,
        colors=not args.no_colors,
        markdown_output=args.markdown,
    )


def main():
    colorama_init()
    args = get_parser().parse_args()
    run_cmd(args)


if __name__ == "__main__":
    main()
