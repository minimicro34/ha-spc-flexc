# FlexC event table

Every event the SPC panel can send over FlexC, as listed by the panel itself
(web page: **Communications → FlexC → Event Profiles →** view a profile **→ Show
Complete Event Table**) on an SPC4300 with firmware 3.14.1. The integration keeps its own descriptions for the events it
already describes and uses the panel's name for every other event
(`custom_components/spc_flexc/flexc/event_table.py`). Events 3502, 3503, 3506
and 3507 show the site's own Partset names on a panel; the default names are given
here.

608 events.

| ID | English | Address type | SIA | CID |
|---|---|---|---|---|
| 1000 | Burglary Alarm [Alarm Zone] | Zone ID | BA | 130/1 |
| 1001 | Burglary Alarm [Entry/Exit Zone] | Zone ID | BA | 134/1 |
| 1002 | Burglary Alarm [Exit Term Zone] | Zone ID | BA | – |
| 1003 | Zone alarm [Fire alarm Zone] | Zone ID | FA | 110/1 |
| 1004 | Burglary Alarm [Fire Exit Zone] | Zone ID | BA | 130/1 |
| 1005 | Zone alarm [Line Zone] | Zone ID | LT | 351/1 |
| 1006 | Zone alarm [Panic Zone] | Zone ID | PA | 120/1 |
| 1007 | Zone alarm [Holdup Zone] | Zone ID | HA | 120/1 |
| 1008 | Zone alarm [Tamper Zone] | Zone ID | TA | 137/1 |
| 1009 | Zone alarm [Tech Zone] | Zone ID | UA | 150/1 |
| 1010 | Zone alarm [Medical Zone] | Zone ID | MA | 100/1 |
| 1011 | Zone alarm [Keyarm Zone] | Zone ID | BA | – |
| 1012 | Zone alarm [Unused Zone] | Zone ID | – | – |
| 1013 | Zone alarm [Shunt Zone] | Zone ID | BA | – |
| 1014 | Zone alarm [X-Shunt Zone] | Zone ID | BA | – |
| 1015 | Zone alarm [Detector Fault Zone] | Zone ID | BT | 380/1 |
| 1016 | Zone alarm [Lock Supervision Zone] | Zone ID | BA | 130/1 |
| 1017 | Burglary Alarm [Seismic Zone] | Zone ID | BA | 130/1 |
| 1019 | Zone alarm [Holdup Fault Zone] | Zone ID | HT | 376/1 |
| 1020 | Zone alarm [Warning Fault Zone] | Zone ID | YA | 380/1 |
| 1021 | Zone alarm [Setting authorisation Zone] | Zone ID | – | – |
| 1022 | Burglary Alarm [Lock element Zone] | Zone ID | – | – |
| 1023 | Burglary Alarm [Glass Break Zone] | Zone ID | BA | 130/1 |
| 1024 | Zone alarm [Water Zone] | Zone ID | WA | 154/1 |
| 1025 | Zone alarm [Heat Zone] | Zone ID | KA | 158/1 |
| 1026 | Zone alarm [Fridge/Freezer Zone] | Zone ID | ZA | 152/1 |
| 1027 | Zone alarm [Gas Zone] | Zone ID | GA | 151/1 |
| 1028 | Zone alarm [Sprinkler Zone] | Zone ID | SA | 213/1 |
| 1029 | Zone alarm [CO Zone] | Zone ID | CY | 162/1 |
| 1100 | Burglary Restoral [Alarm Zone] | Zone ID | BR | 130/3 |
| 1101 | Burglary Restoral [Entry/Exit Zone] | Zone ID | BR | 130/3 |
| 1102 | Burglary Restoral [Exit Term Zone] | Zone ID | BR | – |
| 1103 | Zone restore [Fire Restoral Zone] | Zone ID | FR | 110/3 |
| 1104 | Burglary Restoral [Fire Exit Zone] | Zone ID | BR | 130/3 |
| 1105 | Zone restore [Line Zone] | Zone ID | LR | 351/3 |
| 1106 | Zone restore [Panic Zone] | Zone ID | PR | 120/3 |
| 1107 | Zone restore [Holdup Zone] | Zone ID | HR | 120/3 |
| 1108 | Zone restore [Tamper Zone] | Zone ID | TR | 137/3 |
| 1109 | Zone restore [Tech Zone] | Zone ID | UR | 150/3 |
| 1110 | Zone restore [Medical Zone] | Zone ID | MR | 100/3 |
| 1111 | Zone restore [Keyarm Zone] | Zone ID | BR | – |
| 1112 | Zone restore [Unused Zone] | Zone ID | – | – |
| 1113 | Zone restore [Shunt Zone] | Zone ID | BR | – |
| 1114 | Zone restore [X-Shunt Zone] | Zone ID | BR | – |
| 1115 | Zone restore [Detector Fault Zone] | Zone ID | BJ | 380/3 |
| 1116 | Zone restore [Lock Supervision Zone] | Zone ID | – | – |
| 1117 | Burglary Restoral [Seismic Zone] | Zone ID | BR | 130/3 |
| 1119 | Zone restore [Holdup Fault Zone] | Zone ID | HJ | 376/3 |
| 1120 | Zone restore [Warning Fault Zone] | Zone ID | YH | 380/3 |
| 1121 | Zone restore [Setting authorisation Zone] | Zone ID | – | – |
| 1122 | Burglary Restoral [Lock element Zone] | Zone ID | BR | 130/3 |
| 1123 | Burglary Restoral [Glass Break Zone] | Zone ID | BR | 130/3 |
| 1124 | Zone restore [Water Zone] | Zone ID | WH | 154/3 |
| 1125 | Zone restore [Heat Zone] | Zone ID | KH | 158/3 |
| 1126 | Zone restore [Fridge/Freezer Zone] | Zone ID | ZH | 152/3 |
| 1127 | Zone restore [Gas Zone] | Zone ID | GH | 151/3 |
| 1128 | Zone restore [Sprinkler Zone] | Zone ID | SH | 213/3 |
| 1129 | Zone restore [CO Zone] | Zone ID | CH | 162/3 |
| 1200 | Zone tamper [Alarm Zone] | Zone ID | BT | 144/1 |
| 1201 | Zone tamper [Entry/Exit Zone] | Zone ID | BT | 144/1 |
| 1202 | Zone tamper [Exit Term Zone] | Zone ID | BT | 144/1 |
| 1203 | Zone tamper [Fire Zone] | Zone ID | FT | 144/1 |
| 1204 | Zone tamper [Fire Exit Zone] | Zone ID | BT | 144/1 |
| 1205 | Zone tamper [Line Zone] | Zone ID | BT | 144/1 |
| 1206 | Zone tamper [Panic Zone] | Zone ID | PT | 144/1 |
| 1207 | Zone tamper [Holdup Zone] | Zone ID | HT | 144/1 |
| 1208 | Zone tamper [Tamper Zone] | Zone ID | TA | 144/1 |
| 1209 | Zone tamper [Tech Zone] | Zone ID | UT | 144/1 |
| 1210 | Zone tamper [Medical Zone] | Zone ID | MT | 144/1 |
| 1211 | Zone tamper [Keyarm Zone] | Zone ID | BT | 144/1 |
| 1212 | Zone tamper [Unused Zone] | Zone ID | – | 144/1 |
| 1213 | Zone tamper [Shunt Zone] | Zone ID | BT | 144/1 |
| 1214 | Zone tamper [X-Shunt Zone] | Zone ID | BT | 144/1 |
| 1215 | Zone tamper [Detector Fault Zone] | Zone ID | BT | 144/1 |
| 1216 | Zone tamper [Lock Supervision Zone] | Zone ID | UT | 144/1 |
| 1217 | Zone tamper [Seismic Zone] | Zone ID | BT | 144/1 |
| 1218 | Zone tamper [All Okay Zone] | Zone ID | – | 144/1 |
| 1219 | Zone tamper [Holdup Fault Zone] | Zone ID | HT | 144/1 |
| 1220 | Zone tamper [Warning Fault Zone] | Zone ID | YA | 144/1 |
| 1221 | Zone tamper [Setting authorisation Zone] | Zone ID | UT | 144/1 |
| 1222 | Zone tamper [Lock element Zone] | Zone ID | UT | 144/1 |
| 1223 | Zone tamper [Glass Break Zone] | Zone ID | BT | 144/1 |
| 1300 | Zone tamper Restore [Alarm Zone] | Zone ID | BJ | 144/3 |
| 1301 | Zone tamper Restore [Entry/Exit Zone] | Zone ID | BJ | 144/3 |
| 1302 | Zone tamper Restore [Exit Term Zone] | Zone ID | BJ | 144/3 |
| 1303 | Zone tamper Restore [Fire Zone] | Zone ID | FJ | 144/3 |
| 1304 | Zone tamper Restore [Fire Exit Zone] | Zone ID | BJ | 144/3 |
| 1305 | Zone tamper Restore [Line Zone] | Zone ID | BJ | 144/3 |
| 1306 | Zone tamper Restore [Panic Zone] | Zone ID | PJ | 144/3 |
| 1307 | Zone tamper Restore [Holdup Zone] | Zone ID | HJ | 144/3 |
| 1308 | Zone tamper Restore [Tamper Zone] | Zone ID | TR | 144/3 |
| 1309 | Zone tamper Restore [Tech Zone] | Zone ID | UJ | 144/3 |
| 1310 | Zone tamper Restore [Medical Zone] | Zone ID | MJ | 144/3 |
| 1311 | Zone tamper Restore [Keyarm Zone] | Zone ID | BJ | 144/3 |
| 1312 | Zone tamper Restore [Unused Zone] | Zone ID | – | 144/3 |
| 1313 | Zone tamper Restore [Shunt Zone] | Zone ID | BJ | 144/3 |
| 1314 | Zone tamper Restore [X-Shunt Zone] | Zone ID | BJ | 144/3 |
| 1315 | Zone tamper Restore [Detector Fault Zone] | Zone ID | BJ | 144/3 |
| 1316 | Zone tamper Restore [Lock Supervision Zone] | Zone ID | UJ | 144/3 |
| 1317 | Zone tamper Restore [Seismic Zone] | Zone ID | BJ | 144/3 |
| 1318 | Zone tamper Restore [All Okay Zone] | Zone ID | TR | 144/3 |
| 1319 | Zone tamper Restore [Holdup Fault Zone] | Zone ID | HJ | 144/3 |
| 1320 | Zone tamper Restore [Warning Fault Zone] | Zone ID | YH | 144/3 |
| 1321 | Zone tamper Restore [Setting authorisation Zone] | Zone ID | UJ | 144/3 |
| 1322 | Zone tamper Restore [Lock element Zone] | Zone ID | UJ | 144/3 |
| 1323 | Zone tamper Restore [Glass Break Zone] | Zone ID | BJ | 144/3 |
| 1400 | Zone inhibit [Alarm Zone] | Zone ID | BB | 570/1 |
| 1401 | Zone inhibit [Entry/Exit Zone] | Zone ID | BB | 570/1 |
| 1402 | Zone inhibit [Exit Term Zone] | Zone ID | BB | 570/1 |
| 1403 | Zone inhibit [Fire Zone] | Zone ID | FB | 570/1 |
| 1404 | Zone inhibit [Fire Exit Zone] | Zone ID | BB | 570/1 |
| 1405 | Zone inhibit [Line Zone] | Zone ID | UB | 570/1 |
| 1406 | Zone inhibit [Panic Zone] | Zone ID | PB | 570/1 |
| 1407 | Zone inhibit [Holdup Zone] | Zone ID | HB | 570/1 |
| 1408 | Zone inhibit [Tamper Zone] | Zone ID | TB | 570/1 |
| 1409 | Zone inhibit [Tech Zone] | Zone ID | UB | 570/1 |
| 1410 | Zone inhibit [Medical Zone] | Zone ID | MB | 570/1 |
| 1411 | Zone inhibit [Keyarm Zone] | Zone ID | BB | 570/1 |
| 1412 | Zone inhibit [Unused Zone] | Zone ID | – | 570/1 |
| 1413 | Zone inhibit [Shunt Zone] | Zone ID | BB | 570/1 |
| 1414 | Zone inhibit [X-Shunt Zone] | Zone ID | BB | 570/1 |
| 1415 | Zone inhibit [Detector Fault Zone] | Zone ID | BB | 570/1 |
| 1416 | Zone inhibit [Lock Supervision Zone] | Zone ID | UB | 570/1 |
| 1417 | Zone inhibit [Seismic Zone] | Zone ID | BB | 570/1 |
| 1418 | Zone inhibit [All Okay Zone] | Zone ID | UB | 570/1 |
| 1419 | Zone inhibit [Holdup Fault Zone] | Zone ID | BB | 570/1 |
| 1420 | Zone inhibit [Warning Fault Zone] | Zone ID | BB | 570/1 |
| 1421 | Zone inhibit [Setting authorisation Zone] | Zone ID | UB | 570/1 |
| 1422 | Zone inhibit [Lock element Zone] | Zone ID | UB | 570/1 |
| 1423 | Zone inhibit [Glass Break Zone] | Zone ID | BB | 570/1 |
| 1500 | Zone deinhibit [Alarm Zone] | Zone ID | BU | 570/3 |
| 1501 | Zone deinhibit [Entry/Exit Zone] | Zone ID | BU | 570/3 |
| 1502 | Zone deinhibit [Exit Term Zone] | Zone ID | BU | 570/3 |
| 1503 | Zone deinhibit [Fire Zone] | Zone ID | FU | 570/3 |
| 1504 | Zone deinhibit [Fire Exit Zone] | Zone ID | BU | 570/3 |
| 1505 | Zone deinhibit [Line Zone] | Zone ID | UU | 570/3 |
| 1506 | Zone deinhibit [Panic Zone] | Zone ID | PU | 570/3 |
| 1507 | Zone deinhibit [Holdup Zone] | Zone ID | HU | 570/3 |
| 1508 | Zone deinhibit [Tamper Zone] | Zone ID | TU | 570/3 |
| 1509 | Zone deinhibit [Tech Zone] | Zone ID | UU | 570/3 |
| 1510 | Zone deinhibit [Medical Zone] | Zone ID | MU | 570/3 |
| 1511 | Zone deinhibit [Keyarm Zone] | Zone ID | BU | 570/3 |
| 1512 | Zone deinhibit [Unused Zone] | Zone ID | – | 570/3 |
| 1513 | Zone deinhibit [Shunt Zone] | Zone ID | BU | 570/3 |
| 1514 | Zone deinhibit [X-Shunt Zone] | Zone ID | BU | 570/3 |
| 1515 | Zone deinhibit [Detector Fault Zone] | Zone ID | BU | 570/3 |
| 1516 | Zone deinhibit [Lock Supervision Zone] | Zone ID | UU | 570/3 |
| 1517 | Zone deinhibit [Seismic Zone] | Zone ID | BU | 570/3 |
| 1518 | Zone deinhibit [All Okay Zone] | Zone ID | UU | 570/3 |
| 1519 | Zone deinhibit [Holdup Fault Zone] | Zone ID | BU | 570/3 |
| 1520 | Zone deinhibit [Warning Fault Zone] | Zone ID | BU | 570/3 |
| 1521 | Zone deinhibit [Setting authorisation Zone] | Zone ID | UU | 570/3 |
| 1522 | Zone deinhibit [Lock element Zone] | Zone ID | UU | 570/3 |
| 1523 | Zone deinhibit [Glass Break Zone] | Zone ID | BU | 570/3 |
| 1600 | Zone isolate [Alarm Zone] | Zone ID | BB | 570/1 |
| 1601 | Zone isolate [Entry/Exit Zone] | Zone ID | BB | 570/1 |
| 1602 | Zone isolate [Exit Term Zone] | Zone ID | BB | 570/1 |
| 1603 | Zone isolate [Fire Zone] | Zone ID | FB | 570/1 |
| 1604 | Zone isolate [Fire Exit Zone] | Zone ID | BB | 570/1 |
| 1605 | Zone isolate [Line Zone] | Zone ID | UB | 570/1 |
| 1606 | Zone isolate [Panic Zone] | Zone ID | PB | 570/1 |
| 1607 | Zone isolate [Holdup Zone] | Zone ID | HB | 570/1 |
| 1608 | Zone isolate [Tamper Zone] | Zone ID | TB | 570/1 |
| 1609 | Zone isolate [Tech Zone] | Zone ID | UB | 570/1 |
| 1610 | Zone isolate [Medical Zone] | Zone ID | MB | 570/1 |
| 1611 | Zone isolate [Keyarm Zone] | Zone ID | BB | 570/1 |
| 1612 | Zone isolate [Unused Zone] | Zone ID | – | 570/1 |
| 1613 | Zone isolate [Shunt Zone] | Zone ID | BB | 570/1 |
| 1614 | Zone isolate [X-Shunt Zone] | Zone ID | BB | 570/1 |
| 1615 | Zone isolate [Detector Fault Zone] | Zone ID | BB | 570/1 |
| 1616 | Zone isolate [Lock Supervision Zone] | Zone ID | UB | 570/1 |
| 1617 | Zone isolate [Seismic Zone] | Zone ID | BB | 570/1 |
| 1618 | Zone isolate [All Okay Zone] | Zone ID | UB | 570/1 |
| 1619 | Zone isolate [Holdup Fault Zone] | Zone ID | BB | 570/1 |
| 1620 | Zone isolate [Warning Fault Zone] | Zone ID | BB | 570/1 |
| 1621 | Zone isolate [Setting authorisation Zone] | Zone ID | UB | 570/1 |
| 1622 | Zone isolate [Lock element Zone] | Zone ID | UB | 570/1 |
| 1623 | Zone isolate [Glass Break Zone] | Zone ID | BB | 570/1 |
| 1700 | Zone deisolate [Alarm Zone] | Zone ID | BU | 570/3 |
| 1701 | Zone deisolate [Entry/Exit Zone] | Zone ID | BU | 570/3 |
| 1702 | Zone deisolate [Exit Term Zone] | Zone ID | BU | 570/3 |
| 1703 | Zone deisolate [Fire Zone] | Zone ID | FU | 570/3 |
| 1704 | Zone deisolate [Fire Exit Zone] | Zone ID | BU | 570/3 |
| 1705 | Zone deisolate [Line Zone] | Zone ID | UU | 570/3 |
| 1706 | Zone deisolate [Panic Zone] | Zone ID | PU | 570/3 |
| 1707 | Zone deisolate [Holdup Zone] | Zone ID | HU | 570/3 |
| 1708 | Zone deisolate [Tamper Zone] | Zone ID | TU | 570/3 |
| 1709 | Zone deisolate [Tech Zone] | Zone ID | UU | 570/3 |
| 1710 | Zone deisolate [Medical Zone] | Zone ID | MU | 570/3 |
| 1711 | Zone deisolate [Keyarm Zone] | Zone ID | BU | 570/3 |
| 1712 | Zone deisolate [Unused Zone] | Zone ID | – | 570/3 |
| 1713 | Zone deisolate [Shunt Zone] | Zone ID | BU | 570/3 |
| 1714 | Zone deisolate [X-Shunt Zone] | Zone ID | BU | 570/3 |
| 1715 | Zone deisolate [Detector Fault Zone] | Zone ID | BU | 570/3 |
| 1716 | Zone deisolate [Lock Supervision Zone] | Zone ID | UU | 570/3 |
| 1717 | Zone deisolate [Seismic Zone] | Zone ID | BU | 570/3 |
| 1718 | Zone deisolate [All Okay Zone] | Zone ID | UU | 570/3 |
| 1719 | Zone deisolate [Holdup Fault Zone] | Zone ID | BU | 570/3 |
| 1720 | Zone deisolate [Warning Fault Zone] | Zone ID | BU | 570/3 |
| 1721 | Zone deisolate [Setting authorisation Zone] | Zone ID | UU | 570/3 |
| 1722 | Zone deisolate [Lock element Zone] | Zone ID | UU | 570/3 |
| 1723 | Zone deisolate [Glass Break Zone] | Zone ID | BU | 570/3 |
| 1800 | Trouble [Alarm Zone] | Zone ID | UT | 150/1 |
| 1801 | Trouble [Entry/Exit Zone] | Zone ID | UT | 150/1 |
| 1802 | Trouble [Exit Term Zone] | Zone ID | UT | 150/1 |
| 1803 | Trouble [Fire Zone] | Zone ID | UT | 150/1 |
| 1804 | Trouble [Fire Exit Zone] | Zone ID | UT | 150/1 |
| 1805 | Trouble [Line Zone] | Zone ID | UT | 150/1 |
| 1806 | Trouble [Panic Zone] | Zone ID | UT | 150/1 |
| 1807 | Trouble [Holdup Zone] | Zone ID | UT | 150/1 |
| 1808 | Trouble [Tamper Zone] | Zone ID | UT | 150/1 |
| 1809 | Trouble [Tech Zone] | Zone ID | UT | 150/1 |
| 1810 | Trouble [Medical Zone] | Zone ID | UT | 150/1 |
| 1811 | Trouble [Keyarm Zone] | Zone ID | UT | 150/1 |
| 1812 | Trouble [Unused Zone] | Zone ID | – | 150/1 |
| 1813 | Trouble [Shunt Zone] | Zone ID | UT | 150/1 |
| 1814 | Trouble [X-Shunt Zone] | Zone ID | UT | 150/1 |
| 1815 | Trouble [Detector Fault Zone] | Zone ID | UT | 150/1 |
| 1816 | Trouble [Lock Supervision Zone] | Zone ID | UT | 150/1 |
| 1817 | Trouble [Seismic Zone] | Zone ID | UT | 150/1 |
| 1818 | Trouble [All Okay Zone] | Zone ID | UT | 150/1 |
| 1819 | Trouble [Holdup Fault Zone] | Zone ID | UT | 150/1 |
| 1820 | Trouble [Warning Fault Zone] | Zone ID | UT | 150/1 |
| 1821 | Trouble [Setting authorisation Zone] | Zone ID | UT | 150/1 |
| 1822 | Trouble [Lock element Zone] | Zone ID | UT | 150/1 |
| 1823 | Trouble [Glass Break Zone] | Zone ID | UT | 150/1 |
| 1900 | Trouble restore [Alarm Zone] | Zone ID | UJ | 150/3 |
| 1901 | Trouble restore [Entry/Exit Zone] | Zone ID | UJ | 150/3 |
| 1902 | Trouble restore [Exit Term Zone] | Zone ID | UJ | 150/3 |
| 1903 | Trouble restore [Fire Zone] | Zone ID | UJ | 150/3 |
| 1904 | Trouble restore [Fire Exit Zone] | Zone ID | UJ | 150/3 |
| 1905 | Trouble restore [Line Zone] | Zone ID | UJ | 150/3 |
| 1906 | Trouble restore [Panic Zone] | Zone ID | UJ | 150/3 |
| 1907 | Trouble restore [Holdup Zone] | Zone ID | UJ | 150/3 |
| 1908 | Trouble restore [Tamper Zone] | Zone ID | UJ | 150/3 |
| 1909 | Trouble restore [Tech Zone] | Zone ID | UJ | 150/3 |
| 1910 | Trouble restore [Medical Zone] | Zone ID | UJ | 150/3 |
| 1911 | Trouble restore [Keyarm Zone] | Zone ID | UJ | 150/3 |
| 1912 | Trouble restore [Unused Zone] | Zone ID | UJ | 150/3 |
| 1913 | Trouble restore [Shunt Zone] | Zone ID | UJ | 150/3 |
| 1914 | Trouble restore [X-Shunt Zone] | Zone ID | UJ | 150/3 |
| 1915 | Trouble restore [Detector Fault Zone] | Zone ID | UJ | 150/3 |
| 1916 | Trouble restore [Lock Supervision Zone] | Zone ID | UJ | 150/3 |
| 1917 | Trouble restore [Seismic Zone] | Zone ID | UJ | 150/3 |
| 1918 | Trouble restore [All Okay Zone] | Zone ID | UJ | 150/3 |
| 1919 | Trouble restore [Holdup Fault Zone] | Zone ID | UJ | 150/3 |
| 1920 | Trouble restore [Warning Fault Zone] | Zone ID | UJ | 150/3 |
| 1921 | Trouble restore [Setting authorisation Zone] | Zone ID | UJ | 150/3 |
| 1922 | Trouble restore [Lock element Zone] | Zone ID | UJ | 150/3 |
| 1923 | Trouble restore [Glass Break Zone] | Zone ID | UJ | 150/3 |
| 2000 | Zone walked [Alarm Zone] | Zone ID | TP | 613/1 |
| 2001 | Zone walked [Entry/Exit Zone] | Zone ID | TP | 613/1 |
| 2002 | Zone walked [Exit Term Zone] | Zone ID | TP | – |
| 2003 | Zone walked [Fire Zone] | Zone ID | TP | 614/1 |
| 2004 | Zone walked [Fire Exit Zone] | Zone ID | TP | – |
| 2005 | Zone walked [Line Zone] | Zone ID | TP | – |
| 2006 | Zone walked [Panic Zone] | Zone ID | TP | 615/1 |
| 2007 | Zone walked [Holdup Zone] | Zone ID | TP | – |
| 2008 | Zone walked [Tamper Zone] | Zone ID | TP | 613/1 |
| 2009 | Zone walked [Tech Zone] | Zone ID | TP | – |
| 2010 | Zone walked [Medical Zone] | Zone ID | TP | – |
| 2011 | Zone walked [Keyarm Zone] | Zone ID | TP | – |
| 2012 | Zone walked [Unused Zone] | Zone ID | TP | – |
| 2013 | Zone walked [Shunt Zone] | Zone ID | TP | – |
| 2014 | Zone walked [X-Shunt Zone] | Zone ID | TP | – |
| 2015 | Zone walked [Detector Fault Zone] | Zone ID | TP | – |
| 2016 | Zone walked [Lock Supervision Zone] | Zone ID | TP | – |
| 2017 | Zone walked [Seismic Zone] | Zone ID | TP | 613/1 |
| 2018 | Zone walked [All Okay Zone] | Zone ID | TP | – |
| 2019 | Zone walked [Holdup Fault Zone] | Zone ID | TP | – |
| 2020 | Zone walked [Warning Fault Zone] | Zone ID | TP | – |
| 2021 | Zone walked [Setting authorisation Zone] | Zone ID | TP | – |
| 2022 | Zone walked [Lock element Zone] | Zone ID | TP | – |
| 2023 | Zone walked [Glass Break Zone] | Zone ID | TP | – |
| 2024 | SEISMIC TEST OK | Zone ID | BX | 750/1 |
| 2025 | SEISMIC TEST FAIL | Zone ID | BF | 751/1 |
| 2100 | Zone input open | Zone ID | ZO | – |
| 2101 | Zone input closed | Zone ID | ZC | – |
| 2102 | Zone input shorted | Zone ID | ZX | – |
| 2103 | Zone input disconnected | Zone ID | ZD | – |
| 2104 | Zone input masked | Zone ID | ZM | – |
| 2105 | Zone input fault | Zone ID | ZF | – |
| 2106 | Zone input unstable | Zone ID | ZN | – |
| 2107 | Zone input out of bounds | Zone ID | – | – |
| 2108 | Zone Low battery | Zone ID | XT | – |
| 2109 | Zone Low battery - Restored | Zone ID | XR | – |
| 2110 | Zone input open | Zone ID | ZO | – |
| 2111 | Zone input closed | Zone ID | ZC | – |
| 2112 | Zone input shorted | Zone ID | ZX | – |
| 2113 | Zone input disconnected | Zone ID | ZD | – |
| 2114 | Zone input masked | Zone ID | ZM | – |
| 2115 | Zone input fault | Zone ID | ZF | – |
| 2116 | Zone input unstable | Zone ID | ZN | – |
| 2117 | Zone input out of bounds | Zone ID | – | – |
| 3000 | Entry Granted | Door ID | DG | – |
| 3001 | Entry Denied | Door ID | DD | – |
| 3002 | Exit Granted | Door ID | DG | – |
| 3003 | Exit Denied | Door ID | DD | – |
| 3004 | Door Open too long | Door ID | DN | – |
| 3005 | Left open | Door ID | DN | – |
| 3006 | Door Forced Open | Door ID | DF | – |
| 3007 | Door Normal | Door ID | DO | – |
| 3008 | Door Locked | Door ID | DC | – |
| 3009 | Door Unlocked | Door ID | DO | – |
| 3010 | Door Open | Door ID | DO | – |
| 3011 | Door Closed | Door ID | – | – |
| 3012 | Door Release | Door ID | DX | – |
| 3013 | Alarm restore | Door ID | DR | – |
| 3014 | Unknown card | Door ID | AU | – |
| 3015 | Reader locked | Door ID | RL | – |
| 3016 | Reader unlocked | Door ID | RG | – |
| 3500 | Alarm Confirmed | Area ID | BV | 139/1 |
| 3501 | Unset | Area ID | OG | 401/1 |
| 3502 | Partset A | Area ID | NL | 456/3 |
| 3503 | Partset B | Area ID | NL | 456/3 |
| 3504 | Fullset | Area ID | CG | 401/3 |
| 3505 | Remote Unset | User ID | OQ | – |
| 3506 | Remote Partset A | Area ID | – | – |
| 3507 | Remote Partset B | Area ID | – | – |
| 3508 | Remote Fullset | User ID | CQ | – |
| 3509 | Keyarm [Unset Zone] | Zone ID | OS | – |
| 3510 | Keyarm [Fullset Zone] | Zone ID | CS | – |
| 3511 | Fail to Set | Area ID | CI | 454/1 |
| 3512 | Entry timeout | Area ID | – | – |
| 3513 | Late to Set | Area ID | OT | 452/1 |
| 3514 | Late to unset | Area ID | CT | 452/1 |
| 3515 | Post alarm Unset | Area ID | OG | 401/1 |
| 3516 | Early to set | User ID | CK | 451/3 |
| 3517 | Early to unset | User ID | OK | 451/1 |
| 3518 | Area Alarm Abort | User ID | BC | 406/1 |
| 3519 | Area Walk test Start | Area ID | ZK | 607/1 |
| 3520 | Area Walk test End | Area ID | TC | 607/3 |
| 3521 | All Areas Fullset | Area ID | CL | – |
| 3522 | All Areas Unset | Area ID | OP | – |
| 3523 | Confirmed holdup | Area ID | HV | 129/1 |
| 3524 | Entry Timer Started | Area ID | – | – |
| 3525 | Auto Set | Area ID | CP | 403/3 |
| 3526 | Auto Unset | Area ID | OA | 403/1 |
| 3527 | Unset Delayed START | Area ID | – | – |
| 3528 | Unset Delayed CANCELLED | Area ID | – | – |
| 4000 | User Duress | User ID | HA | 121/1 |
| 4001 | User Duress Restore | User ID | HR | 121/3 |
| 4002 | USER PANIC | User ID | PA | 120/1 |
| 4003 | User accessing | User ID | JP | – |
| 4004 | User accessing end | User ID | ZG | – |
| 4005 | Fob low batt Fault | User ID | XT | – |
| 4006 | Fob low batt Restore | User ID | XR | – |
| 4007 | User code changed | User ID | JV | – |
| 4008 | USER PANIC Restore | User ID | PR | 120/3 |
| 4009 | User Medic | User ID | MA | 100/1 |
| 4010 | User Medic Restore | User ID | MR | 100/3 |
| 4011 | User Holdup | User ID | HA | 120/1 |
| 4012 | User Holdup Restore | User ID | HR | 120/3 |
| 4013 | User Webpass Changed | User ID | JV | – |
| 4014 | Grant Access | User ID | – | – |
| 4015 | Engineer access revoked | User ID | – | – |
| 4100 | MDT PANIC | User ID | PA | 120/1 |
| 4101 | MDT TILT | User ID | MA | 100/1 |
| 4102 | MDT BELT | User ID | HA | 120/1 |
| 4103 | Man down panic Restore | User ID | PR | 120/3 |
| 4104 | MDT TILT Restore | User ID | MR | 100/3 |
| 4105 | MDT BELT Restore | User ID | HR | 120/3 |
| 4106 | MDT TAMPER | User ID | – | – |
| 4200 | WPA Panic | WPA ID | PA | 120/1 |
| 4201 | WPA Panic Restore | WPA ID | PR | 120/3 |
| 4202 | WPA Holdup | WPA ID | HA | 120/1 |
| 4203 | WPA Holdup Restore | WPA ID | HR | 120/3 |
| 4204 | WPA suspicion | WPA ID | – | – |
| 4205 | WPA suspicion Restore | WPA ID | – | – |
| 4206 | WPA Medical | WPA ID | MA | 100/1 |
| 4207 | WPA Medical Restore | WPA ID | MR | 100/3 |
| 5000 | PSU Mains Fault | - | AT | 301/1 |
| 5001 | PSU Mains Restore | - | AR | 301/3 |
| 5002 | PSU Mains Inhibit | - | – | – |
| 5003 | PSU Mains Deinhibit | - | – | – |
| 5004 | PSU Mains Isolate | - | – | – |
| 5005 | PSU Mains Deisolate | - | – | – |
| 5006 | PSU Battery Fault | - | YT | 311/1 |
| 5007 | PSU Battery Restore | - | YR | 311/3 |
| 5008 | PSU Battery Inhibit | - | – | – |
| 5009 | PSU Battery Deinhibit | - | – | – |
| 5010 | PSU Battery Isolate | - | – | – |
| 5011 | PSU Battery Deisolate | - | – | – |
| 5012 | PSU EXT Fuse Fault | - | YP | 312/1 |
| 5013 | PSU EXT Fuse Restore | - | YQ | 312/3 |
| 5014 | PSU EXT Fuse Inhibit | - | – | – |
| 5015 | PSU EXT Fuse Deinhibit | - | – | – |
| 5016 | PSU EXT Fuse Isolate | - | – | – |
| 5017 | PSU EXT Fuse Deisolate | - | – | – |
| 5018 | PSU INT Fuse Fault | - | YP | 312/1 |
| 5019 | PSU INT Fuse Restore | - | YQ | 312/3 |
| 5020 | PSU INT Fuse Inhibit | - | – | – |
| 5021 | PSU INT Fuse Deinhibit | - | – | – |
| 5022 | PSU INT Fuse Isolate | - | – | – |
| 5023 | PSU INT Fuse Deisolate | - | – | – |
| 5024 | PSU Aux. Fuse Fault | - | YP | 312/1 |
| 5025 | PSU Aux. Fuse Restore | - | YQ | 312/3 |
| 5026 | PSU Aux. Fuse Inhibit | - | – | – |
| 5027 | PSU Aux. Fuse Deinhibit | - | – | – |
| 5028 | PSU Aux. Fuse Isolate | - | – | – |
| 5029 | PSU Aux. Fuse Deisolate | - | – | – |
| 5030 | PSU Fault Fault | - | YP | 300/1 |
| 5031 | PSU Fault Restore | - | YQ | 300/3 |
| 5032 | PSU Fault Inhibit | - | – | – |
| 5033 | PSU Fault Deinhibit | - | – | – |
| 5034 | PSU Fault Isolate | - | – | – |
| 5035 | PSU Fault Deisolate | - | – | – |
| 5036 | PSU Output fault | Expander | OU | – |
| 5037 | PSU Output ok | Expander | OV | – |
| 5038 | PSU Low Voltage Trouble | Expander | XB | – |
| 5039 | PSU Low Voltage Restoral | Expander | XC | – |
| 5040 | Low battery Fault | Expander | XD | – |
| 5041 | Low battery Restore | Expander | XG | – |
| 5042 | PSU Discharged | Expander | XK | – |
| 5100 | RF JAM Fault | - | XQ | 344/1 |
| 5101 | RF JAM Restore | - | XH | 344/3 |
| 5102 | RF JAM Inhibit | - | – | – |
| 5103 | RF JAM Deinhibit | - | – | – |
| 5104 | RF JAM Isolate | - | – | – |
| 5105 | RF JAM Deisolate | - | – | – |
| 5106 | Antenna Tamper Fault | - | XS | – |
| 5107 | Antenna Tamper Restore | - | XJ | – |
| 5108 | Antenna Tamper Inhibit | - | – | – |
| 5109 | Antenna Tamper Deinhibit | - | – | – |
| 5110 | Antenna Tamper Isolate | - | – | – |
| 5111 | Antenna Tamper Deisolate | - | – | – |
| 5200 | Bell Tamper Fault | - | YA | 320/1 |
| 5201 | Bell Tamper Restore | - | YH | 320/3 |
| 5202 | Bell Tamper Inhibit | - | – | – |
| 5203 | Bell Tamper Deinhibit | - | – | – |
| 5204 | Bell Tamper Isolate | - | – | – |
| 5205 | Bell Tamper Deisolate | - | – | – |
| 5206 | Cabinet Tamper Fault | - | TA | 137/1 |
| 5207 | Cabinet Tamper Restore | - | TR | 137/3 |
| 5208 | Cabinet Tamper Inhibit | - | – | – |
| 5209 | Cabinet Tamper Deinhibit | - | – | – |
| 5210 | Cabinet Tamper Isolate | - | – | – |
| 5211 | Cabinet Tamper Deisolate | - | – | – |
| 5212 | AUX 1 Tamper Fault | - | TA | 137/1 |
| 5213 | AUX 1 Tamper Restore | - | TR | 137/3 |
| 5214 | AUX 1 Tamper Inhibit | - | – | – |
| 5215 | AUX 1 Tamper Deinhibit | - | – | – |
| 5216 | AUX 1 Tamper Isolate | - | – | – |
| 5217 | AUX 1 Tamper Deisolate | - | – | – |
| 5218 | AUX 2 Tamper Fault | - | TA | 137/1 |
| 5219 | AUX 2 Tamper Restore | - | TR | 137/3 |
| 5220 | AUX 2 Tamper Inhibit | - | – | – |
| 5221 | AUX 2 Tamper Deinhibit | - | – | – |
| 5222 | AUX 2 Tamper Isolate | - | – | – |
| 5223 | AUX 2 Tamper Deisolate | - | – | – |
| 5300 | XBUS cable fault | - | ES | 333/1 |
| 5301 | XBUS cable fault Restore | - | EJ | 333/3 |
| 5302 | XBUS cable fault Inhibit | - | – | – |
| 5303 | XBUS cable fault Deinhibit | - | – | – |
| 5304 | XBUS cable fault Isolate | - | – | – |
| 5305 | XBUS cable fault Deisolate | - | – | – |
| 5306 | XBUS comms lost Fault | Expander | EM | 333/1 |
| 5307 | XBUS comms lost Restore | Expander | EN | 333/3 |
| 5308 | XBUS comms lost Inhibit | Expander | – | – |
| 5309 | XBUS comms lost Deinhibit | Expander | – | – |
| 5310 | XBUS comms lost Isolate | Expander | – | – |
| 5311 | XBUS comms lost Deisolate | Expander | – | – |
| 5312 | XBUS tamper Fault | Expander | ES | 341/1 |
| 5313 | XBUS tamper Restore | Expander | EJ | 341/3 |
| 5314 | XBUS tamper Inhibit | Expander | – | – |
| 5315 | XBUS tamper Deinhibit | Expander | – | – |
| 5316 | XBUS tamper Isolate | Expander | – | – |
| 5317 | XBUS tamper Deisolate | Expander | – | – |
| 5318 | XBUS fuse fault | Expander | ET | 333/1 |
| 5319 | XBUS fuse fault Restore | Expander | ER | 333/3 |
| 5320 | XBUS fuse fault Inhibit | Expander | – | – |
| 5321 | XBUS fuse fault Deinhibit | Expander | – | – |
| 5322 | XBUS fuse fault Isolate | Expander | – | – |
| 5323 | XBUS fuse fault Deisolate | Expander | – | – |
| 5324 | XBUS mains fault | Expander | AT | 342/1 |
| 5325 | XBUS mains fault Restore | Expander | AR | 342/3 |
| 5326 | XBUS mains fault Inhibit | Expander | – | – |
| 5327 | XBUS mains fault Deinhibit | Expander | – | – |
| 5328 | XBUS mains fault Isolate | Expander | – | – |
| 5329 | XBUS mains fault Deisolate | Expander | – | – |
| 5330 | XBUS battery Fault | Expander | ET | 338/1 |
| 5331 | XBUS battery Restore | Expander | ER | 338/3 |
| 5332 | XBUS battery Inhibit | Expander | – | – |
| 5333 | XBUS battery Deinhibit | Expander | – | – |
| 5334 | XBUS battery Isolate | Expander | – | – |
| 5335 | XBUS battery Deisolate | Expander | – | – |
| 5336 | XBUS rf jamming Fault | Expander | XQ | 344/1 |
| 5337 | XBUS rf jamming Restore | Expander | XH | 344/3 |
| 5338 | XBUS rf jamming Inhibit | Expander | – | – |
| 5339 | XBUS rf jamming Deinhibit | Expander | – | – |
| 5340 | XBUS rf jamming Isolate | Expander | – | – |
| 5341 | XBUS rf jamming Deisolate | Expander | – | – |
| 5342 | X-BUS Antenna Tamper Fault | Expander | XS | 341/1 |
| 5343 | X-BUS Antenna Tamper Restore | Expander | XJ | 341/3 |
| 5344 | X-BUS Antenna Tamper Inhibit | Expander | – | – |
| 5345 | X-BUS Antenna Tamper Deinhibit | Expander | – | – |
| 5346 | X-BUS Antenna Tamper Isolate | Expander | – | – |
| 5347 | X-BUS Antenna Tamper Deisolate | Expander | – | – |
| 5348 | XBUS panic Alarm | Expander | PA | 120/1 |
| 5349 | XBUS panic Restore | Expander | PR | 120/3 |
| 5350 | XBUS fire Alarm | Expander | FA | 110/1 |
| 5351 | XBUS fire Restore | Expander | FR | 110/3 |
| 5352 | XBUS medical Alarm | Expander | MA | 100/1 |
| 5353 | XBUS medical Restore | Expander | MR | 100/3 |
| 5354 | XBUS PSU Fault | Expander | ET | 330/1 |
| 5355 | XBUS PSU Fault Restore | Expander | ER | 330/3 |
| 5356 | XBUS PSU Fault Inhibit | Expander | – | – |
| 5357 | XBUS PSU Fault Deinhibit | Expander | – | – |
| 5358 | XBUS PSU Fault Isolate | Expander | – | – |
| 5359 | XBUS PSU Fault Deisolate | Expander | – | – |
| 5360 | Keypad locked | Expander | ZE | – |
| 5361 | Keypad Not Locked Out | Expander | KG | – |
| 5362 | WEB locked | - | WW | – |
| 5363 | WEB Not Locked Out | - | WX | – |
| 6000 | Network Fail | - | XY | – |
| 6001 | Network Restoral | - | XZ | – |
| 6002 | FlexC ATP Down | ATP ID | NT | – |
| 6003 | FlexC ATP Up | ATP ID | NR | – |
| 6004 | FlexC ATS Down | - | YC | – |
| 6005 | FlexC ATS Up | - | YK | – |
| 6006 | FlexC Manual Test | User ID | RX | 601/1 |
| 6007 | FlexC Automatic Testcall Active | ATP ID | RP | 602/1 |
| 6008 | EDP Receiver Down | EDP Receiver ID | NT | – |
| 6009 | EDP Receiver Up | EDP Receiver ID | NR | – |
| 6010 | EDP Manual Test | EDP Receiver ID | RX | 601/1 |
| 6011 | EDP Automatic Testcall | EDP Receiver ID | RP | 602/1 |
| 6012 | Modem Manual Test | User ID | RX | 601/1 |
| 6013 | Modem Automatic Testcall | Modem ID | RP | 602/1 |
| 6015 | FlexC Automatic Testcall | ATP ID | RP | 602/1 |
| 6100 | Modem 1 Fault | Modem ID | YS | 351/1 |
| 6101 | Modem 1 Fault Restore | Modem ID | YK | 351/3 |
| 6102 | Modem 1 Fault Inhibit | Modem ID | – | – |
| 6103 | Modem 1 Fault Deinhibit | Modem ID | – | – |
| 6104 | Modem 1 Fault Isolate | Modem ID | – | – |
| 6105 | Modem 1 Fault Deisolate | Modem ID | – | – |
| 6106 | Modem 1 Line Fault | Modem ID | LT | 351/1 |
| 6107 | Modem 1 Line Fault Restore | Modem ID | LR | 351/3 |
| 6108 | Modem 1 Line Fault Inhibit | Modem ID | – | – |
| 6109 | Modem 1 Line Fault Deinhibit | Modem ID | – | – |
| 6110 | Modem 1 Line Fault Isolate | Modem ID | – | – |
| 6111 | Modem 1 Line Fault Deisolate | Modem ID | – | – |
| 6112 | Modem 2 Fault | Modem ID | YS | 352/1 |
| 6113 | Modem 2 Fault Restore | Modem ID | YK | 351/3 |
| 6114 | Modem 2 Line Fault | Modem ID | LT | 352/1 |
| 6115 | Modem 2 Line Fault Restore | Modem ID | LR | 351/3 |
| 6116 | Modem 2 Fault Inhibit | Modem ID | – | – |
| 6117 | Modem 2 Fault Deinhibit | Modem ID | – | – |
| 6118 | Modem 2 Fault Isolate | Modem ID | – | – |
| 6119 | Modem 2 Fault Deisolate | Modem ID | – | – |
| 6120 | Modem 2 Line Fault Inhibit | Modem ID | – | – |
| 6121 | Modem 2 Line Fault Deinhibit | Modem ID | – | – |
| 6122 | Modem 2 Line Fault Isolate | Modem ID | – | – |
| 6123 | Modem 2 Line Fault Deisolate | Modem ID | – | – |
| 7000 | System boot | - | RR | 305/1 |
| 7001 | User Code Tamper | - | JA | 461/1 |
| 7002 | Date Changed | - | JT | 625/1 |
| 7003 | Engineer Enabled | - | LB | 466/1 |
| 7004 | Engineer Disabled | - | LX | 466/3 |
| 7005 | Hardware fault | - | HF | – |
| 7006 | Alert (Close Alert) | Alert ID | SD | – |
| 7007 | Alert (Open Alert) | Alert ID | SO | – |
| 7008 | Alert (X-BUS Alert Expander) | Alert ID | NB | – |
| 7009 | Alert (X-BUS Alert Expander) | Alert ID | NO | – |
| 7010 | Code Tamper System | - | JA | 461/1 |
| 7011 | Configuration changed | - | – | – |
| 7012 | Code Tamper X-BUS | Expander | JA | 461/1 |
| 7013 | Mapping gate ON | - | – | – |
| 7014 | Mapping gate OFF | - | – | – |
| 8000 | Camera Offline | Camera ID | CV | – |
| 8001 | Camera Online | Camera ID | CU | – |
| 8002 | Service Engineer Access Request | User ID | SE | – |
| 8003 | Hold-up Information | - | HD | – |
| 8004 | Wireless Lost Event | Zone ID | BZ | 147/1 |
| 8005 | Wireless Supervision Restore | Zone ID | WZ | 147/3 |
| 8006 | Two Way Wireless Tamper | Area ID | TA | 137/1 |
| 8007 | Two Way Wireless Tamper Restore | Area ID | TR | 137/3 |
| 8008 | Two Way Wireless Tamper Inhibit | Area ID | – | – |
| 8009 | Two Way Wireless Tamper Deinhibit | Area ID | – | – |
| 8010 | Two Way Wireless Tamper Isolate | Area ID | – | – |
| 8011 | Two Way Wireless Tamper Deisolate | Area ID | – | – |
| 8012 | Two way wireless low battery | Area ID | XT | – |
| 8013 | Two way wireless low battery Battery Restoral | Area ID | XR | – |
| 8014 | Two Way Wireless Trouble | Area ID | UT | 150/1 |
| 8015 | Two Way Wireless Trouble Restore | Area ID | UJ | 150/3 |
| 8016 | Two Way Wireless Trouble Inhibit | Area ID | – | – |
| 8017 | Two Way Wireless Trouble Deinhibit | Area ID | – | – |
| 8018 | Two Way Wireless Trouble Isolate | Area ID | – | – |
| 8019 | Two Way Wireless Trouble Deisolate | Area ID | – | – |
| 8020 | Two Way Wireless DC Supply | Area ID | AT | – |
| 8021 | Two Way Wireless DC Supply Restore | Area ID | AT | – |
| 8022 | Two Way Wireless DC Supply Inhibit | Area ID | – | – |
| 8023 | Two Way Wireless DC Supply Deinhibit | Area ID | – | – |
| 8024 | Two Way Wireless DC Supply Isolate | Area ID | – | – |
| 8025 | Two Way Wireless DC Supply Deisolate | Area ID | – | – |
| 8026 | Two Way Wireless Medical Alarm | Area ID | MA | 100/1 |
| 8027 | Two Way Wireless Medical Restore | Area ID | MR | 100/3 |
| 8028 | Two Way Wireless Fire Alarm | Area ID | FA | 110/1 |
| 8029 | Two Way Wireless Fire Restore | Area ID | FR | 110/3 |
| 8030 | Two Way Wireless Panic Alarm | Area ID | PA | 120/1 |
| 8031 | Two Way Wireless Panic Restore | Area ID | PR | 120/3 |
| 8032 | Two Way Wireless code tamper Alarm | Area ID | JA | 461/1 |
| 8033 | Two Way Wireless code tamper Restore | Area ID | JA | 461/3 |
| 8034 | Two Way Wireless code tamper Inhibit | Area ID | – | – |
| 8035 | Two Way Wireless code tamper Deinhibit | Area ID | – | – |
| 8036 | Two Way Wireless code tamper Isolate | Area ID | – | – |
| 8037 | Two Way Wireless code tamper Deisolate | Area ID | – | – |
| 8038 | Keypad locked | Area ID | ZE | – |
| 8039 | Keypad Not Locked Out | Area ID | KG | – |
