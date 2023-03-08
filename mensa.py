import argparse
from colorama import init as colorama_init
from colorama import Fore
from colorama import Style
from html.parser import HTMLParser
import requests

meat_allergens = set(
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
)

ovo_lacto_allergens = set(
    [
        "Eier (42)",
        "Milch (46)",
    ]
)

other_allergens = set(
    [
        # "fleischlose Kost (V)",
        # "Vegan (Veg)",
    ]
)

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


class Meal:
    def __init__(self, title: str) -> None:
        self.title = title
        self.allergens: list[str] = []
        self.additives: list[str] = []
        self.student_price: int | None = None
        self.staff_price: int | None = None
        self.guest_price: int | None = None

    def add_allergen(self, allergen: str) -> None:
        self.allergens.append(allergen)

    def add_additive(self, additive: str) -> None:
        self.additives.append(additive)


class Category:
    def __init__(self, title) -> None:
        self.title = title
        self.meals = []

    def add_meal(self, meal: Meal) -> None:
        self.meals.append(meal)


class SimpleMensaResponseParser(HTMLParser):
    def __init__(self, lang: str, verbose: bool = False):
        super().__init__()
        self.curr_category: Category | None = None
        self.curr_meal: Meal | None = None

        self.last_tag: str | None = None
        self.last_nonignored_tag: str | None = None
        self.categories = []
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


def main(
    date: str,
    canteen: str,
    filtered_categories: list[str],
    language: str,
    filter_mode: str | None = None,
    url: str = "https://www.studierendenwerk-bonn.de/index.php?eID=meals",
    verbose: bool = False,
) -> None:
    filter_str = f" [{filter_mode}]" if filter_mode else ""
    print(
        f"{Fore.YELLOW}Mensa {canteen} – {date}{filter_str} [{language}]{Style.RESET_ALL}"
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

    queried_categories = [
        cat for cat in parser.categories if cat.title not in filtered_categories
    ]
    maxlen_catname = max(len(cat.title) for cat in queried_categories)

    interesting_allergens = meat_allergens | ovo_lacto_allergens | other_allergens

    if filter_mode is None:
        remove_allergens = set()
    elif filter_mode == "vegetarian":
        remove_allergens = meat_allergens
    elif filter_mode == "vegan":
        remove_allergens = meat_allergens | ovo_lacto_allergens
    else:
        raise NotImplementedError(filter_mode)

    for cat in queried_categories:
        filtered_meals = [
            meal for meal in cat.meals if not set(meal.allergens) & remove_allergens
        ]

        if not filtered_meals:
            continue

        cat_str = cat.title.ljust(maxlen_catname + 1)
        print(f"{Fore.GREEN}{cat_str}{Style.RESET_ALL}", end="")

        for meal_idx, meal in enumerate(filtered_meals):
            # do not indent first line
            if meal_idx:
                print(" " * (maxlen_catname + 1), end="")
            print(
                f"{Fore.BLUE}{meal.title} {Fore.CYAN}({meal.student_price/100:.2f}€)",
                end="",
            )
            if set(meal.allergens) & interesting_allergens:
                print(
                    f" {Fore.RED}[{', '.join(al for al in meal.allergens if al in interesting_allergens)}]",
                    end="",
                )
            print(f"{Style.RESET_ALL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser("mensa")
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument(
        "--vegan", action="store_true", help="Only show vegan options"
    )
    filter_group.add_argument(
        "--vegetarian", action="store_true", help="Only show vegetarian options"
    )
    parser.add_argument(
        "--mensa", choices=canteen_id_dict.keys(), type=str, default="CAMPO"
    )
    parser.add_argument(
        "--filter-categories",
        nargs="*",
        default=["Buffet", "Dessert"],
        help="Categories to hide.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="The date to query for. Defaults to today.",
    )

    lang_group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "--lang",
        choices=["de", "en"],
        default="de",
        help="The language of the meal plan to query",
    )

    args = parser.parse_args()

    if args.date is None:
        from datetime import datetime

        date = datetime.today().strftime("%Y-%m-%d")
    else:
        date = args.date

    if args.vegan:
        filter_mode = "vegan"
    elif args.vegetarian:
        filter_mode = "vegetarian"
    else:
        filter_mode = None

    main(
        date=date,
        canteen=args.mensa,
        language=args.lang,
        filtered_categories=args.filter_categories,
        filter_mode=filter_mode,
    )
