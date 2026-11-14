# Reproducibility report

Scale: starter. Seed: 20261022. Comparison seed: 20261023. SHA-256 values are shown as the first 16 hex characters.

Overall: PASS

## Same seed, two runs

| File | Rows | Run 1 | Run 2 | Match |
|---|---|---|---|---|
| data/customer_site.csv | 55 | 7cb01f6cb4ca95df | 7cb01f6cb4ca95df | pass |
| data/delivery.csv | 200 | a82ed290fec40297 | a82ed290fec40297 | pass |
| data/delivery_outcome.csv | 105 | ff20e66e44d482c6 | ff20e66e44d482c6 | pass |
| data/delivery_status_event.csv | 614 | 0f47f1399c2200a3 | 0f47f1399c2200a3 | pass |
| data/driver.csv | 12 | 5e0754e191aa6976 | 5e0754e191aa6976 | pass |
| data/json/customer_site.json | 55 | 6008924441da1d67 | 6008924441da1d67 | pass |
| data/json/delivery.json | 200 | 58aa8f30e8b987a1 | 58aa8f30e8b987a1 | pass |
| data/json/delivery_outcome.json | 105 | ada987360bb16ed4 | ada987360bb16ed4 | pass |
| data/json/delivery_status_event.json | 614 | b2cb835006a53398 | b2cb835006a53398 | pass |
| data/json/driver.json | 12 | 563c62481d5990ac | 563c62481d5990ac | pass |
| data/json/order.json | 180 | 8e953fa62aee0b15 | 8e953fa62aee0b15 | pass |
| data/json/route.json | 29 | 0fcbf1e2457d156a | 0fcbf1e2457d156a | pass |
| data/json/route_stop.json | 106 | 2673da2247b320a7 | 2673da2247b320a7 | pass |
| data/json/shift.json | 30 | 2d37a2c9e69d5e0a | 2d37a2c9e69d5e0a | pass |
| data/json/time_window.json | 200 | c99d53534a0912b9 | c99d53534a0912b9 | pass |
| data/json/traffic_scenario.json | 15 | 6bb0600b7e92c2ec | 6bb0600b7e92c2ec | pass |
| data/json/travel_time_matrix.json | 2970 | 78cc6a910261085b | 78cc6a910261085b | pass |
| data/json/vehicle.json | 10 | 89000845e4a81b78 | 89000845e4a81b78 | pass |
| data/json/vehicle_capacity.json | 10 | 482304a43ab52735 | 482304a43ab52735 | pass |
| data/manifest.json | n/a | 88435132bff2134d | 88435132bff2134d | pass |
| data/order.csv | 180 | c431b1be9c9c4cde | c431b1be9c9c4cde | pass |
| data/route.csv | 29 | e1db83bdbd2566dd | e1db83bdbd2566dd | pass |
| data/route_stop.csv | 106 | 2a1bc06b32ac65cb | 2a1bc06b32ac65cb | pass |
| data/shift.csv | 30 | c01dc593fef5d184 | c01dc593fef5d184 | pass |
| data/time_window.csv | 200 | 2048c58e1f2b355b | 2048c58e1f2b355b | pass |
| data/traffic_scenario.csv | 15 | 3ba16e9e940584b0 | 3ba16e9e940584b0 | pass |
| data/travel_time_matrix.csv | 2970 | 109cbfe949af9eb3 | 109cbfe949af9eb3 | pass |
| data/vehicle.csv | 10 | e0fc70b26264249c | e0fc70b26264249c | pass |
| data/vehicle_capacity.csv | 10 | 5d421493b919708c | 5d421493b919708c | pass |
| ground_truth/ground_truth.csv | 23 | 54177d07afc97529 | 54177d07afc97529 | pass |
| sql/schema.sql | None | dc9eca1756458644 | dc9eca1756458644 | pass |
| sql/seed.sql | 4536 | 801d9988a4c141b0 | 801d9988a4c141b0 | pass |

## Different seed

| File | Seed 20261022 | Seed 20261023 | Expected | Result |
|---|---|---|---|---|
| data/customer_site.csv | 7cb01f6cb4ca95df | b099de279cf656a3 | different | pass |
| data/delivery.csv | a82ed290fec40297 | 2cab834bb9f2adc8 | different | pass |
| data/delivery_outcome.csv | ff20e66e44d482c6 | 8f89161ff022bbfc | different | pass |
| data/delivery_status_event.csv | 0f47f1399c2200a3 | b0f22426eee7356a | different | pass |
| data/driver.csv | 5e0754e191aa6976 | 44ec970a173d7302 | different | pass |
| data/json/customer_site.json | 6008924441da1d67 | 26ad1fad4eff9e0e | different | pass |
| data/json/delivery.json | 58aa8f30e8b987a1 | 7ef772e9a857b2b1 | different | pass |
| data/json/delivery_outcome.json | ada987360bb16ed4 | 07c10fcb6f9e1250 | different | pass |
| data/json/delivery_status_event.json | b2cb835006a53398 | e04e9eab7c6c11d7 | different | pass |
| data/json/driver.json | 563c62481d5990ac | 85b35e8e42bf6d1d | different | pass |
| data/json/order.json | 8e953fa62aee0b15 | 4fa55e1fc80289c4 | different | pass |
| data/json/route.json | 0fcbf1e2457d156a | 0d527a0d115aa698 | different | pass |
| data/json/route_stop.json | 2673da2247b320a7 | 660f2788ffd50628 | different | pass |
| data/json/shift.json | 2d37a2c9e69d5e0a | d1391fb1f8f256e9 | different | pass |
| data/json/time_window.json | c99d53534a0912b9 | 838b7804154277b3 | different | pass |
| data/json/traffic_scenario.json | 6bb0600b7e92c2ec | 9fa3e5c0bdfcd28e | different | pass |
| data/json/travel_time_matrix.json | 78cc6a910261085b | 3a3bf579e6a4add0 | different | pass |
| data/json/vehicle.json | 89000845e4a81b78 | 4291c2ecb7e9e6f9 | different | pass |
| data/json/vehicle_capacity.json | 482304a43ab52735 | 32a5ddcdb30a12b7 | different | pass |
| data/manifest.json | 88435132bff2134d | a015b72fcb3d79fc | different | pass |
| data/order.csv | c431b1be9c9c4cde | d1655a0ec9769d86 | different | pass |
| data/route.csv | e1db83bdbd2566dd | 3950ff4285f1d6e3 | different | pass |
| data/route_stop.csv | 2a1bc06b32ac65cb | d97187b72ebffa8e | different | pass |
| data/shift.csv | c01dc593fef5d184 | 1b9e2e67c701f34e | different | pass |
| data/time_window.csv | 2048c58e1f2b355b | 78317b743b9ccc2a | different | pass |
| data/traffic_scenario.csv | 3ba16e9e940584b0 | c25acdfc7880cd83 | different | pass |
| data/travel_time_matrix.csv | 109cbfe949af9eb3 | f45ddb2a5c9ebde2 | different | pass |
| data/vehicle.csv | e0fc70b26264249c | 19112516f82f2b44 | different | pass |
| data/vehicle_capacity.csv | 5d421493b919708c | 7822aaf939e53554 | different | pass |
| ground_truth/ground_truth.csv | 54177d07afc97529 | 61fcbbaaa7b421ea | different | pass |
| sql/schema.sql | dc9eca1756458644 | dc9eca1756458644 | same | pass |
| sql/seed.sql | 801d9988a4c141b0 | 1dad1028f478199a | different | pass |

## Manifest

Every checksum listed in data/manifest.json matches the file on disk: pass.
