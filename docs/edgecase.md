# Edge cases

## AI-Powered Restaurant Recommendation System

This file lists the edge cases and corner scenarios for the system in [architecture.md](architecture.md) and [phasewise-implementation.md](phasewise-implementation.md). Use it when a result looks wrong: find the symptom, confirm the expected behavior, then check the module named in the case.

Each case has an id so a bug report can cite it, for example `EC-FIL-08`.

## How to look up a bug

| What you see | Start here |
| --- | --- |
| Ingest crashes, or the Parquet file is missing or corrupt | [Ingest and cleaning](#ingest-and-cleaning) |
| The API process exits as soon as it starts | [Startup and settings](#startup-and-settings) |
| A restaurant is missing, duplicated, or in the wrong neighborhood | [Identity and merge](#identity-and-merge) |
| Too many matches, too few matches, or a surprising price or rating | [Filters](#filters) |
| A card shows a restaurant or a price the model invented | [Recommendation engine](#recommendation-engine) |
| Explanations are blank, or the page says reasons are unavailable | [Model failures](#model-failures) |
| HTTP 422, an empty 200, or HTTP 503 | [HTTP API](#http-api) |
| The form or the cards look wrong | [Web UI](#web-ui) |
| Phone numbers, menus, or private wishes show up in logs or prompts | [Privacy](#privacy) |

`candidate_count` is the number of restaurants that survived the filters, before the short list is cut. The model sees at most `max_candidates` of those rows (default 15). The page shows at most `limit` cards (default 5). A search with 100 matches still shows 5 cards. That is the contract, not a dropped result.

## Startup and settings

| ID | Situation | Expected behavior | If this is the bug, check |
| --- | --- | --- | --- |
| EC-CFG-01 | No `.env` file and no Parquet file | `from app.main import app` still succeeds. Tests can collect. | `app/main.py` importing the catalog at import time |
| EC-CFG-02 | `MAX_CANDIDATES` is set in the environment | The running process uses that value | `Settings` reading the environment only at construction |
| EC-CFG-03 | `MAX_CANDIDATES` is below 1 or above 30 | Settings reject the value | `app/config.py` bounds |
| EC-CFG-04 | `DEFAULT_LIMIT` is below 1 or above 10 | Settings reject the value | `app/config.py` bounds |
| EC-CFG-05 | `LLM_TIMEOUT_SECONDS` is 0 or negative | Settings reject the value. A live call uses a positive timeout, default 30 | `app/config.py` and the HTTP client timeout |
| EC-CFG-06 | `budget_bounds` is called with a band other than `low`, `medium`, or `high` | `ValueError` | `budget_bounds` |
| EC-CFG-07 | `CATALOG_PATH` is relative | It is resolved from the repository root, the parent of `app/`, not from a random working directory | `app/config.py` path resolution |
| EC-CFG-08 | Budget bounds are left at the defaults | Low is 1–500, medium is 501–1,000, high starts at 1,001 | `tests/test_config.py` |
| EC-CFG-09 | `budget_low_max` is greater than or equal to `budget_medium_max` | Medium matches nothing, because its range runs from `budget_low_max + 1` through `budget_medium_max` | The two budget settings |
| EC-CFG-10 | Model variables are empty during unit tests | Filter tests and service tests still pass. A live model call is the only path that needs them | Tests constructing a fake client |
| EC-CFG-11 | The Parquet file was replaced while the API is running | The process keeps the catalog it loaded at startup until it is restarted | Restart after ingest |

## Ingest and cleaning

Source: Hugging Face `ManikaSaini/zomato-restaurant-recommendation`, split `train`, 51,717 listings. The first ingest needs a network connection. Later ingests may use the Hugging Face cache. Every successful run replaces `data/processed/restaurants.parquet` and prints the raw count, the merged count, and the dropped count. The merged count is lower than 51,717. A second run produces the same ids.

### Ratings

`parse_rating` accepts a number from 0 to 5.

| ID | Input | Expected |
| --- | --- | --- |
| EC-ING-01 | `4.1/5` | `4.1` |
| EC-ING-02 | `4.1 /5` | `4.1` |
| EC-ING-03 | A bare `0`, `4`, or `5` | That number. `0` and `5` are valid ratings |
| EC-ING-04 | `NEW`, `-`, or blank | `None` |
| EC-ING-05 | Below 0 or above 5 | `None` |
| EC-ING-06 | A word such as `Excellent` | `None` |
| EC-ING-07 | Whitespace around a valid rating, such as ` 4.1/5 ` | `4.1` after trimming. If these become missing ratings, the parser is not trimming |

A missing rating stays null in Parquet. It is not stored as `0`.

### Cost and votes

| ID | Input | Expected |
| --- | --- | --- |
| EC-ING-08 | `800` | Cost `800` |
| EC-ING-09 | `1,200` or `1, 200` | Cost `1200` after commas and whitespace are removed |
| EC-ING-10 | Blank or non-numeric cost | `None` |
| EC-ING-11 | `0` or a negative cost | `None`, because only a positive integer is stored |
| EC-ING-12 | A decimal string such as `800.5` | `None` when it cannot be read as a positive integer. The row is kept, with no cost |
| EC-ING-13 | Votes `775` or `2,556` | `775` or `2556` |
| EC-ING-14 | Missing votes | `0` |
| EC-ING-15 | One votes cell is garbage | That row still ingests. Votes become `0`. One bad cell does not abort the file |

The source column name is `approx_cost(for two people)`, including the parentheses. Reading a shortened name stores null costs for every restaurant, and every budget filter then drops them.

### Lists, flags, and text

| ID | Situation | Expected |
| --- | --- | --- |
| EC-ING-16 | Cuisine, rest type, or dishes is null | Empty list |
| EC-ING-17 | `North Indian, Chinese,` or ` North Indian , , Chinese ` | `["North Indian", "Chinese"]`. Empty tokens are dropped and surrounding spaces are trimmed |
| EC-ING-18 | `Italian, Cafe, Italian` | `["Italian", "Cafe"]`. First-seen order is kept |
| EC-ING-19 | `online_order` or `book_table` is `Yes`, `yes`, or `YES` | `true` |
| EC-ING-20 | The flag is `No`, blank, or any other word | `false` |
| EC-ING-21 | A flag has surrounding spaces, such as ` Yes ` | `true` after trimming |
| EC-ING-22 | A name or address contains broken encoding, such as a mangled `Café` | `ftfy` repairs it, then internal whitespace is collapsed and the ends are trimmed |
| EC-ING-23 | The name or the address is empty or only whitespace after repair | The group is dropped and counted in the dropped total |
| EC-ING-24 | `phone` or `menu_item` is present on the raw row | Those columns are never read. They are absent from the catalog, the prompt, and the API |

### Reviews

| ID | Situation | Expected |
| --- | --- | --- |
| EC-ING-25 | A normal `reviews_list` with two or more reviews | The first two review bodies, each with a leading `RATED` label removed, whitespace collapsed, and length at most 280 characters |
| EC-ING-26 | One review, or a body that is empty after the label is removed | At most the usable bodies. An empty body is not stored |
| EC-ING-27 | The field is not a Python list, or `ast.literal_eval` fails | Empty snippet list. The restaurant is still saved |
| EC-ING-28 | The field is longer than 100,000 characters, including rows past one megabyte | A bounded scan reads the first snippets. The whole literal is not parsed. Ingest finishes |
| EC-ING-29 | Several duplicate listings each have reviews | The merged card keeps the first two snippets encountered in the group, not two from every listing |

### Identity and merge

The merge key is the repaired, casefolded name plus the repaired, casefolded address, with whitespace collapsed. The id is the first 12 hexadecimal characters of the SHA-256 of that normalized name, a newline, and that normalized address.

| ID | Situation | Expected |
| --- | --- | --- |
| EC-MRG-01 | The same restaurant appears once per `listed_in(type)` and `listed_in(city)` | One catalog row |
| EC-MRG-02 | The copies differ only by letter case or extra spaces | They merge, and both runs produce the same id |
| EC-MRG-03 | The same name has two different addresses | Two restaurants and two ids |
| EC-MRG-04 | Encoding repair makes two spellings identical | They merge, because repair happens before the id is hashed |
| EC-MRG-05 | Copies have different vote counts | Rating, cost, online order, table booking, url, display name, and display address come from the copy with more votes |
| EC-MRG-06 | Votes tie and only one copy has a rating | That rated copy supplies the display fields |
| EC-MRG-07 | Votes tie and both copies have a rating, or neither does | One whole copy supplies rating, cost, flags, url, and display name together. Cost from one copy is not paired with the rating from the other |
| EC-MRG-08 | Copies disagree on neighborhood | The neighborhood on the card is the winner's `location`. Neighborhoods are not unioned |
| EC-MRG-09 | Copies list different cuisines, rest types, dishes, and listing types | Those lists are unioned in first-seen order |
| EC-MRG-10 | The union of liked dishes is longer than 12 | The card keeps the first 12 |
| EC-MRG-11 | Two different name-and-address pairs produce the same 12-character id | Treat it as an id collision. Facts from two restaurants would share one id. Compare the full SHA-256 before shortening |
| EC-MRG-12 | Ingest is killed while writing Parquet | The API later refuses to start, because a partial file is unreadable. Rerun ingest. A failed run should leave the previous good file in place, or exit without publishing a truncated file |

`listed_in(city)` has 30 values and `location` has 93. Filters use `location`. A bug that filters on `listed_in(city)` drops or mixes neighborhoods.

## Catalog load

| ID | Situation | Expected behavior | If this is the bug, check |
| --- | --- | --- | --- |
| EC-CAT-01 | The Parquet file is missing | `CatalogStore.load` raises. The API process exits non-zero and logs the path. It does not build an empty store | Startup lifespan in `app/main.py` |
| EC-CAT-02 | The Parquet file is unreadable | Same exit as a missing file | A crashed ingest, or a path that points at a directory |
| EC-CAT-03 | The file loads and contains zero restaurants | The process exits. `/api/health` is not served. Health requires a count greater than zero | Ingest dropped every row, or the file is the wrong dataset |
| EC-CAT-04 | Health on a good catalog | `{"status": "ok", "restaurants": <count>}` with `count` greater than zero | `GET /api/health` |
| EC-CAT-05 | Locations index | Sorted unique neighborhoods from `location`. `All Bangalore` is not one of those neighborhoods | `CatalogStore.locations` |
| EC-CAT-06 | Cuisines index | Each cuisine token once per restaurant, most common first. A repeated token on one restaurant adds one, because ingest already de-duplicated tokens | Count logic |
| EC-CAT-07 | Two cuisines have the same count | Order is stable between process restarts. Use the cuisine name as the tie-break | Sort key |
| EC-CAT-08 | List columns and null ratings or costs | They round-trip through Parquet as lists and nulls, not as the string `"None"` | The Parquet schema written by ingest |

## Filters

Filters run in this order: location, cuisine, minimum rating, budget, sort, cap. An optional field that is missing or blank skips that step. Extra wishes never add or remove rows.

The store returns the capped rows and the pre-cap count. An unknown neighborhood passed straight to `filter` returns an empty list. The HTTP layer turns that same unknown neighborhood into 422 before `filter` runs.

### Location

| ID | Situation | Expected |
| --- | --- | --- |
| EC-FIL-01 | `location` is `Banashankari` | Every returned row has that neighborhood |
| EC-FIL-02 | `location` is `banashankari` or `BANASHANKARI` | Same rows as `Banashankari` |
| EC-FIL-03 | `location` is ` All Bangalore ` or `all bangalore` | The neighborhood filter is skipped after trim and case folding. Rows may come from every neighborhood |
| EC-FIL-04 | `location` is a real city outside this dataset, such as Mysore, and the caller is the store | Empty list and candidate count 0 |
| EC-FIL-05 | The same Mysore value is sent to `POST /api/recommendations` | 422, and the model is not called |
| EC-FIL-06 | Only a neighborhood is set | Cuisine, rating, and budget stay open. Null ratings and null costs remain. Rows are sorted by rating, then votes |

### Cuisine

Match is a case-insensitive substring on any cuisine token. `Italian` matches `Cafe, Mexican, Italian`.

| ID | Situation | Expected |
| --- | --- | --- |
| EC-FIL-07 | Cuisine `italian` | Same rows as `Italian` |
| EC-FIL-08 | Cuisine `Indian` | North Indian, South Indian, and Indian all match, because the token contains `Indian` |
| EC-FIL-09 | Cuisine is a very short fragment, such as `a` | Every token containing that fragment matches. A huge result is the contains-rule, not a broken filter |
| EC-FIL-10 | Cuisine is empty or only spaces | Treated as unset. The cuisine step is skipped |
| EC-FIL-11 | A restaurant has an empty cuisine list and the user named a cuisine | That restaurant is excluded |

### Rating

| ID | Situation | Expected |
| --- | --- | --- |
| EC-FIL-12 | Minimum rating is omitted | Rows with a null rating stay in the list and sort after every rated row |
| EC-FIL-13 | Minimum rating is `0` | `0` is a real filter. Rated rows stay. Null ratings are removed. `0` is inside 0–5, so the API accepts it |
| EC-FIL-14 | Minimum rating equals a restaurant's rating, including `4.0` and `5` | That restaurant stays. The comparison is greater-than-or-equal |
| EC-FIL-15 | Minimum rating is `5` | Only restaurants rated exactly 5 stay |
| EC-FIL-16 | A row has a null rating and a minimum is set | The row is removed, even when location, cuisine, and budget match |
| EC-FIL-17 | Two rows share a rating | The one with more votes comes first |
| EC-FIL-18 | Two rows share a rating and a vote count | Their relative order is stable across calls, using id or original catalog order as the tie-break |
| EC-FIL-19 | Minimum rating is below 0 or above 5, including `6` and `-0.1` | The API returns 422 and does not filter or call the model |

### Budget

Default bands: low is 1–500, medium is 501–1,000, high is 1,001 and above. Bounds are inclusive on low and medium.

| ID | Cost for two | Budget | Expected |
| --- | --- | --- | --- |
| EC-FIL-20 | 500 | low | Kept |
| EC-FIL-21 | 500 | medium | Removed |
| EC-FIL-22 | 501 | low | Removed |
| EC-FIL-23 | 501 | medium | Kept |
| EC-FIL-24 | 1,000 | medium | Kept |
| EC-FIL-25 | 1,000 | high | Removed |
| EC-FIL-26 | 1,001 | high | Kept |
| EC-FIL-27 | 1,001 | medium | Removed |
| EC-FIL-28 | null | any selected budget | Removed |
| EC-FIL-29 | null | budget omitted | Kept |
| EC-FIL-30 | any | budget omitted or blank on the form | Budget step skipped. The UI omits the field. The token sent by the API is `low`, `medium`, or `high` |

`Low` with a capital L is outside the token set and returns 422. The form sends the lowercase token, not the visible label.

### Cap and count

| ID | Situation | Expected |
| --- | --- | --- |
| EC-FIL-31 | More than 15 rows survive | The returned list has length 15. `candidate_count` is the larger pre-cap total. The model never sees past the 15 |
| EC-FIL-32 | Exactly 15 rows survive | List length and `candidate_count` are both 15 |
| EC-FIL-33 | Fewer than 15 rows survive, including exactly 1 | The list contains all of them. `candidate_count` equals that length |
| EC-FIL-34 | Zero rows survive | Empty list, `candidate_count` 0. The model is not called |
| EC-FIL-35 | `All Bangalore` with no cuisine, rating, or budget | The whole city is eligible, then cut to the 15 highest ratings. A low-rated restaurant will not be offered. That is the cap |
| EC-FIL-36 | Extra wishes say "only quick service" or "not this cuisine" | The hard-filtered rows stay. Wishes affect explanation and model order only. `Quick Bites`, online order, and table booking are not hard filters |
| EC-FIL-37 | `limit` is 10 while 100 rows match | `candidate_count` is 100, the model sees 15, and the response contains at most 10 cards |

## Recommendation engine

Card name, location, cuisines, rating, votes, and cost are copied from the catalog row for the returned id. The model supplies rank, explanation, and summary.

### Prompt

| ID | Situation | Expected |
| --- | --- | --- |
| EC-REC-01 | A candidate has a null rating or a null cost | The prompt includes the name and omits that number. It does not invent `0` or a placeholder score |
| EC-REC-02 | Extra wishes are set | Those words appear in the user message |
| EC-REC-03 | Extra wishes are empty | The prompt is still valid |
| EC-REC-04 | A decoy phone number or menu is attached to the row | Neither appears in the prompt |
| EC-REC-05 | Wishes contain quotes, newlines, or text that looks like JSON or an instruction to add a restaurant | The wishes stay in the user message as data. Any id the model returns that is not on the short list is dropped |
| EC-REC-06 | Wishes are exactly 500 characters | Accepted and sent |
| EC-REC-07 | The candidate list is empty | No prompt is built and the client is not called. Summary is `No restaurants matched these choices.` `explanations_available` is false |

### Model output

The parser accepts a raw JSON object and a string wrapped in a `json` fence. Timeout, HTTP failure, and unparseable output raise `LlmError`.

| ID | Situation | Expected |
| --- | --- | --- |
| EC-REC-08 | The model ranks known ids in an order that differs from rating | The cards follow the model's order. Each card's rating and cost still equal the catalog |
| EC-REC-09 | The model returns an id that was not in the short list | That id is discarded |
| EC-REC-10 | The model returns one valid id and one unknown id, and `limit` is larger | The unknown id is absent. Remaining cards are filled from the short list in catalog order, with an empty explanation |
| EC-REC-11 | Every returned id is unknown, or the recommendations array is empty | The response is filled from the short list in catalog order, up to `limit`, with empty explanations |
| EC-REC-12 | The same id appears twice | One card for that restaurant |
| EC-REC-13 | Ranks are missing, duplicated, or start above 1 | The surviving items are ordered by the given rank, then renumbered from 1 with no gaps |
| EC-REC-14 | The model returns more items than `limit` | The response is cut to `limit` after invalid ids are removed |
| EC-REC-15 | The model writes a different rating or price inside the explanation sentence | The card's `rating` and `cost_for_two` stay on the catalog values. Disagreement inside the sentence is model text, not the card fact |
| EC-REC-16 | The explanation is only whitespace | It is stored empty. The UI shows "A written reason is unavailable." |
| EC-REC-17 | JSON is missing `summary` or `recommendations`, or the body is empty, prose, or truncated | `LlmError`, then the catalog fallback |
| EC-REC-18 | An id comes back as a number, or with different capitalization | It does not match the catalog id and is dropped |
| EC-REC-19 | The endpoint accepts `response_format` | The request asks for a JSON object. The parser still accepts raw JSON and a fenced JSON string when the endpoint ignores that option |

### Model failures

`LlmError` covers timeout, connection failure, an HTTP error such as 401, 429, or 500, an unreachable `LLM_BASE_URL`, a missing key on a live call, and unparseable output.

| ID | Situation | Expected |
| --- | --- | --- |
| EC-REC-20 | The model fails and the short list has rows | HTTP 200. Cards follow catalog order, already sorted by rating and votes, cut to `limit`. Explanations are empty. `explanations_available` is false. The summary says written reasons are unavailable |
| EC-REC-21 | The model fails and the short list is empty | This path does not call the model. HTTP 200 and an empty list, not a model error |
| EC-REC-22 | The model succeeds for some cards and the service pads the rest to reach `limit` | `explanations_available` is false for the whole response, because at least one card was filled from the catalog. Explanations that the model did write stay on those cards |
| EC-REC-23 | The model fails and the store itself cannot return rows | HTTP 503. A normal model failure with candidates stays 200 |
| EC-REC-24 | The call runs longer than `LLM_TIMEOUT_SECONDS` | The client raises `LlmError` and the fallback in EC-REC-20 is returned. The page's loading state ends with that response |
| EC-REC-25 | Logs for the request | Location, candidate count, and latency are logged. The raw wishes are not. The log has their length and a hash |

## HTTP API

Validation happens before the recommendation service runs. A rejected body does not call the model.

| ID | Request | Expected |
| --- | --- | --- |
| EC-API-01 | `location` omitted | 422 |
| EC-API-02 | `location` is not `All Bangalore` and not a catalog neighborhood | 422, model not called |
| EC-API-03 | A known neighborhood with different letter case | 200 and that neighborhood's rows |
| EC-API-04 | `budget` outside `low`, `medium`, `high`, including `Low` or `cheap` | 422 |
| EC-API-05 | `budget` omitted | 200, budget filter skipped |
| EC-API-06 | `budget` is an empty string | 422. The UI omits the field instead of sending an empty string |
| EC-API-07 | `min_rating` omitted | 200, rating filter skipped |
| EC-API-08 | `min_rating` is `0` or `5` | 200, and the inclusive filter from EC-FIL-13 or EC-FIL-15 |
| EC-API-09 | `min_rating` is `6` or `-0.1` | 422 |
| EC-API-10 | `preferences` length is 500 | 200 |
| EC-API-11 | `preferences` length is 501 | 422 |
| EC-API-12 | `preferences` is only spaces | Treated as unset after trimming |
| EC-API-13 | `limit` omitted | Treated as 5 |
| EC-API-14 | `limit` is `1` or `10` | 200, at most that many cards |
| EC-API-15 | `limit` is `0` or `11` | 422 |
| EC-API-16 | Valid filters match nothing | 200, `candidate_count` 0, `recommendations` `[]`, `explanations_available` false, summary `No restaurants matched these choices.` Model not called |
| EC-API-17 | Valid filters match, and the model returns a ranking | 200. Card facts exist on the matching catalog rows |
| EC-API-18 | `GET /api/locations` | `All Bangalore` is first. The remaining names are sorted. `All Bangalore` appears once |
| EC-API-19 | `GET /api/cuisines` | Objects of `name` and `count`, most common first. No blank cuisine name |
| EC-API-20 | Catalog file renamed, then the process is started | The process exits. `/api/health` is not served |

`applied_filters` includes the preferences that were actually set. An omitted budget, cuisine, or rating is absent from that object.

## Web UI

The page loads neighborhoods from `GET /api/locations` and cuisine suggestions from `GET /api/cuisines`. It posts only the fields the person set. It keeps no restaurant list of its own. Refreshing the page clears the previous cards.

| ID | Situation | Expected |
| --- | --- | --- |
| EC-UI-01 | The page opens against a healthy API | The neighborhood control includes `All Bangalore` first and Banashankari. Cuisine suggestions load |
| EC-UI-02 | `/api/locations` or `/api/cuisines` fails | The page shows that the service is unavailable. It does not submit an empty neighborhood |
| EC-UI-03 | Neighborhood is left unset | The required-field message appears, and no recommendation request is sent |
| EC-UI-04 | Budget is left blank | The POST body has no `budget` field |
| EC-UI-05 | Cuisine is typed in a different case, or is a value absent from the suggestions | The text is sent as typed. An unknown cuisine that matches nothing returns the empty 200 state, not 422 |
| EC-UI-06 | Minimum rating is left empty | The POST body has no `min_rating` field |
| EC-UI-07 | Extra wishes reach 500 characters | The text area stops at 500. A longer value pasted into a hand-built request is the API's 422 in EC-API-11 |
| EC-UI-08 | How many is left at the default | The request uses 5 |
| EC-UI-09 | Submit is clicked twice | The button is disabled and the page says results are being prepared until the response arrives |
| EC-UI-10 | The model takes up to its timeout | Loading continues until the API returns the fallback cards. Loading does not remain after that response |
| EC-UI-11 | A response arrives with cards | Summary first, then cards in `rank` order. Each card shows rank, name, cuisines as comma-separated words, rating, cost in rupees, neighborhood, and explanation |
| EC-UI-12 | `rating` is null | The card shows "No rating yet" |
| EC-UI-13 | `cost_for_two` is null | The card shows "Cost unavailable" |
| EC-UI-14 | `explanation` is empty | The card shows "A written reason is unavailable." |
| EC-UI-15 | `explanations_available` is false and cards are present | A note says written reasons are unavailable and the list is ordered by rating. Per-card text still follows EC-UI-14 |
| EC-UI-16 | `recommendations` is empty | The summary, the filters that were sent, and an invitation to widen the search. No cards |
| EC-UI-17 | The API returns 422 | Field errors appear next to the form. Previous cards are not presented as the new answer |
| EC-UI-18 | The browser cannot reach the API, or the API returns 503 | The page says the service is unavailable. The form stays usable for another try |
| EC-UI-19 | The page is refreshed | The result area is clear |
| EC-UI-20 | The viewport is narrowed to a phone width | The form and cards stack in one column without overlapping |
| EC-UI-21 | Ingest finishes and the page is reloaded, but the API process was not restarted | The dropdown and the cards still come from the catalog loaded at process start. Restart the API, then reload the page |
| EC-UI-22 | The person changes the form during a request | The submit button stays disabled until the current request finishes, so a slower response cannot overwrite a newer search |

## Privacy

| ID | Situation | Expected |
| --- | --- | --- |
| EC-PRV-01 | A raw row has a phone number and a menu | Neither is in Parquet, the prompt, or the recommendation JSON |
| EC-PRV-02 | Review text is longer than a snippet | The catalog and the prompt hold at most two snippets of 280 characters. The rest of `reviews_list` is discarded at ingest |
| EC-PRV-03 | Wishes may describe a personal occasion | Request logs store the length and a hash, not the sentence. Exception logs follow the same limit |
| EC-PRV-04 | The model is asked to repeat hidden fields | The prompt never received phone numbers, full reviews, or menus, so the card cannot gain them from the catalog join |

## Worked examples

These combinations are the ones most often mistaken for bugs.

| Example | Inputs | What should happen |
| --- | --- | --- |
| Happy path | Banashankari, Italian, medium, minimum 4, limit 5 | Every card is in Banashankari, has a cuisine token containing Italian, costs 501–1,000 where a cost is present, and is rated at least 4. There are at most 5 cards. Facts match the catalog ids |
| Boundary price | Cost is exactly 500, 501, 1,000, or 1,001 | 500 is low. 501 and 1,000 are medium. 1,001 is high |
| New and unpriced | Rating `NEW`, cost blank, neighborhood set, no other filters | The restaurant can appear, with "No rating yet" and "Cost unavailable", sorted after rated restaurants |
| New and unpriced with filters | The same restaurant, plus a minimum rating or any budget | The restaurant is excluded |
| City-wide | `All Bangalore` and no other filters | The 15 best-rated restaurants in the city are eligible. The page shows the top `limit` after ranking |
| Nothing matches | A rare cuisine in a small neighborhood with a high minimum rating | HTTP 200, no cards, no model call, and the UI invites a wider search |
| Model down | A search that has matches, with `LLM_BASE_URL` unreachable or `LLM_API_KEY` empty | HTTP 200, cards in rating order, the unavailable-reasons note, and empty explanations |
| Invented restaurant | The model names a place that failed the filters | That place is absent. If the list is then short, catalog rows from the short list fill it |
| Stale server | Ingest completes and the browser is reloaded | Results stay on the old catalog until the API process is restarted |
