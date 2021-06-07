## Separate datasets

## libraries
library(tidyverse)

## data
longData <- read.csv("longTimeseries.csv", stringsAsFactors = F)

## create lake name CSV
lakeNames <- longData %>% dplyr::select(lake, lakecode, other_lakenames)
lakeNames <- lakeNames[!duplicated(lakeNames),] ## drop duplicates
allNames <- lakeNames %>% mutate(other_lakenames = strsplit(other_lakenames, ";")) %>% unnest() %>% arrange(lake) %>%  data.frame()

write.csv(allNames, "database//AllLakeNames.csv", row.names=FALSE)


## Create Coordinate CSV
coords <- longData %>% select(lake, latitude, longitude)
coords <- coords[!duplicated(coords),] ## drop coordinates

write.csv(coords, "database//LakeCoordinates.csv", row.names=FALSE)


## Create master datafile
reducedData <- longData %>% select(-lakecode, -latitude, -longitude, -other_lakenames)
write.csv(reducedData, "database//MainDataset.csv", row.names=FALSE)
