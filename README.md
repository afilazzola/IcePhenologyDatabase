
# A long-term database on ice phenology of lakes around the world

![](lakeIce.jpg)

### Collaborators and Contributors

- Sapna Sharma
- Thi Nguyen, 
- Alessandro Filazzola 
- M. Arshad Imrit
- Kevin Blagrave
- Damien Bouffard 
- Julia Daly
- Harley Feldman
- Natalie Felsine
- Harrie-Jan Hendricks-Franssen
- Nikolay Granin
- Richard Hecock
- Jan Henning L’Abée-Lund
- Ed Hopkins
- Tom Hoverstad
- Neil Howk
- Paulette Janssen
- Johanna Korhonen
- Hilmar J. Malmquist
- Wlodzimierz Marszelewski
- Shin-Ichiro Matsuzaki
- Yuichi Miyabara
- Kiyoshi Miyasaka
- Alexander Mills
- Joe Norton
- Lolita Olson
- Ted Peters
- David C. Richardson
- Dale Robertson
- Lars Rudstam
- Tom Skramstad
- Larry Smisek
- Danielle Wain
- Holly Waterfield
- Gesa Weyhenmeyer
- Brendan Wiltse
- Huaxia Yao
- Andry Zhdanov
- John J. Magnuson



### Data

The data within this database are separated into three main files and one ancillary file. 
- *MainDataset.csv*: has the lake ice phenology for all 69 lakes.
- *LakeCharacteristics.csv*: has the physical characteristics and coordinates of the lakes in the database.
- *AllLakeNames.csv*: has all alternate names of lakes used in the database.
- *69_lakes_ts_minimal.csv*: has all the lake ice phenology but in wide format where each column corresponds to a freeze date for years where the lake was intermittent. 

### Scripts

The *qaqc.r* and *separateMain.r* files are used for converted to *69_lakes_ts_minimal.csv* into "long" format where only one each column represents ice on and ice off dates. The *qaqc.r* file also performs some basic quality control and assurance of the dataset. There are two files, *create_lake_ice_time_series.py* and *additional_functions.py* that consolated lake names, conduct some quality control, and were responsible for the original data aggregation across multiple files. 


