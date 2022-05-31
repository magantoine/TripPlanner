# %load_ext sparkmagic.magics

# +
import os
from IPython import get_ipython
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

username = os.environ['RENKU_USERNAME']
server = "http://iccluster029.iccluster.epfl.ch:8998"

get_ipython().run_cell_magic(
    'spark',
    line='config', 
    cell="""{{ "name": "{0}-final-project", "executorMemory": "4G", "executorCores": 4, "numExecutors": 10, "driverMemory": "4G"}}""".format(username)
)

# -

get_ipython().run_line_magic(
    "spark", "add -s {0}-final-project -l python -u {1} -k".format(username, server)
)

# + language="spark"
# from functools import reduce
# from math import sin, cos, sqrt, atan2, radians
# import pyspark.sql.functions as F
# -

# # Stops processing
# We first filter stops within 15km of Zurich HB 

# + language="spark"
# stops = spark.read.csv("/data/sbb/csv/allstops/stop_locations.csv")

# + language="spark"
# oldColumns = stops.schema.names
# newColumns = ["STOP_ID", "STOP_NAME", "STOP_LAT", "STOP_LON", "LOCATION_TYPE", "PARENT_STATION"]
#
# stops = reduce(lambda data, idx: data.withColumnRenamed(oldColumns[idx], newColumns[idx]), xrange(len(oldColumns)), stops)
# stops.printSchema()
# stops.show()

# + language="spark"
#
# @F.udf
# def distance_gps(coordinate_struct):
#     """Return the distance between two GPS coordinates in km"""
#     
#     # approximate radius of earth in km
#     R = 6373.0
#     
#     lat1=radians(float(coordinate_struct[0]))
#     lon1=radians(float(coordinate_struct[1]))
#     lat2=radians(float(coordinate_struct[2]))
#     lon2=radians(float(coordinate_struct[3]))
#     
#     dlon = lon2 - lon1
#     dlat = lat2 - lat1
#
#     #StackOverflow : https://stackoverflow.com/a/19412565
#     a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
#     c = 2 * atan2(sqrt(a), sqrt(1 - a))
#
#     return R * c

# + language="spark"
# hb_df = stops.filter(stops.STOP_NAME == "Zürich HB")
# hb_df.show(1)

# + language="spark"
# ZURICH_HB_LAT=47.3781762039461
# ZURICH_HB_LON=8.54021154209037
#
# stops_hb = stops.withColumn('ZHB_LAT', F.lit(ZURICH_HB_LAT))\
#     .withColumn('ZHB_LON', F.lit(ZURICH_HB_LON))
#     
# stops_hb = stops_hb.withColumn('distance_hb',distance_gps(F.struct(stops_hb.STOP_LAT, stops_hb.STOP_LON, stops_hb.ZHB_LAT, stops_hb.ZHB_LON)))

# + language="spark"
# stops_hb.sample(0.001).show(10)

# + language="spark"
# THRESHOLD = 15
# stops_in_radius = stops_hb.filter(stops_hb.distance_hb<THRESHOLD)
# stops_in_radius.count()
# -

# # Stop times
# We can now use the previous table to filter the arrival times to keep only trips within the 15km radius

# + language="spark"
# stopt = spark.read.orc("/data/sbb/part_orc/stop_times")
# stopt.printSchema()

# + language="spark"
# stopt.show()

# + language="spark"
# stopt.count()

# + language="spark"
# # Within the week specified by the instructions, only Wednesday contains data, 13/05/2020
# stopt = stopt.filter("year == 2020").filter("month == 5").filter("day >= 13").filter("day < 17")
# stopt.count()

# + language="spark"
# stoptime_in_radius = stopt.join(stops_in_radius, on="stop_id",how="inner")
# print(stoptime_in_radius.count())
# stoptime_in_radius.show(3)

# + magic_args="-o stop_id_in_radius_list" language="spark"
# stop_id_in_radius_list = stops_in_radius.select(stops_in_radius.STOP_ID)
# -

stop_id_in_radius_list.to_csv("../data/stop_ids_in_radius.csv", index=False)

# # Walking distances
# Finally, we will create the walking paths between stations less than 10mins of walk from each other

# + language="spark"
# print(stops_in_radius.count())
# stops_in_radius.show(3)

# + language="spark"
# stopw = stops_in_radius.select(["STOP_ID", "STOP_NAME", "STOP_LAT", "STOP_LON", "PARENT_STATION"])
# stopw.show(5)

# + language="spark"
# stopw2 = stopw.withColumnRenamed("STOP_ID","STOP_ID_2")\
#                 .withColumnRenamed("STOP_NAME","STOP_NAME_2")\
#                 .withColumnRenamed("STOP_LAT","STOP_LAT_2")\
#                 .withColumnRenamed("STOP_LON","STOP_LON_2")\
#                 .withColumnRenamed("PARENT_STATION","PARENT_STATION_2")
# stopw_cross = stopw.crossJoin(stopw2)
# size = stopw_cross.count()
# stopw_cross.show(3)

# + language="spark"
# max_walk_distance_km = 0.5
# stopw_dist = stopw_cross.withColumn('walk_distance',
#                                     distance_gps(F.struct(stopw_cross.STOP_LAT, stopw_cross.STOP_LON, 
#                                                           stopw_cross.STOP_LAT_2, stopw_cross.STOP_LON_2)))
# stopw_dist_500m = stopw_dist.filter(stopw_dist.walk_distance <= max_walk_distance_km)\
#                             .filter(stopw_dist.STOP_NAME != stopw_dist.STOP_NAME_2).cache()
# stopw_dist_500m.show()

# + language="spark"
# stopw_dist_500m.sample(0.001).show(5)

# + language="spark"
# stopw_dist_500m.count()

# + magic_args="-o stopw_dist_500m -n -1" language="spark"
# stopw_dist_500m
# -

print(len(stopw_dist_500m),"No duplicate : ",len(stopw_dist_500m.drop_duplicates(subset=["STOP_NAME", "STOP_NAME_2"])))
# Dropping duplicates
stopw_dist_500m = stopw_dist_500m.drop_duplicates(subset=["STOP_NAME", "STOP_NAME_2"])
stopw_dist_500m.head()

# +
# 50m/ minute walking speed, computing m.s-1
walk_speed = 50 / 60

stopw_dist_500m["walk_time"] = stopw_dist_500m["walk_distance"] * walk_speed * 1000
# -

stopw_dist_500m = stopw_dist_500m[["STOP_NAME", "STOP_NAME_2", "walk_distance", "walk_time"]].copy()
stopw_dist_500m.to_csv("../data/walking_stops_pairs.csv")

# # Model delay distributions

from scipy.stats import expon
import numpy as np
from scipy.optimize import curve_fit
from datetime import datetime


# + language="spark"
# ## SPARK IMPORTS
# from functools import reduce
# from pyspark.sql.types import ArrayType, StringType
# from pyspark.sql.functions import *
#
# REMOTE_PATH = "/group/abiskop1/project_data/"

# + language="spark"
# real_time = spark.read.orc("/data/sbb/part_orc/istdaten").dropna()
#
# arrivals = spark.read.csv(REMOTE_PATH + "arrivalsRouteStops.csv", header='true', inferSchema='true')
# arrivals = arrivals.withColumn("route_id", udf(lambda end_id : end_id.split("$")[0])(col("end_route_stop_id")))
#
# print("The Schema is :")
# real_time

# + language="spark"
# mapping =    [['BETRIEBSTAG', 'date'],
#     ['FAHRT_BEZEICHNER', "trip_id"],
#     ['BETREIBER_ABK', 'operator'],
#     ["BETREIBER_NAME", "operator_name"],
#     ["PRODUCT_ID", "type_transport"],
#     ["LINIEN_ID"," for trains, this is the train number"],
#     ["LINIEN_TEXT","type_service_1"], 
#     ["VERKEHRSMITTEL_TEXT","type_service_2"],
#     ["ZUSATZFAHRT_TF","additional_trip"],
#     ["FAELLT_AUS_TF","trip_failed"],
#     ["HALTESTELLEN_NAME","STOP_NAME"],
#     ["ANKUNFTSZEIT","arrival_time_schedule"],
#     ["AN_PROGNOSE","arrival_time_actual"],
#     ["AN_PROGNOSE_STATUS","measure_method_arrival"],
#     ["ABFAHRTSZEIT","departure_time_schedule"],
#     ["AB_PROGNOSE","departure_time_actual"],
#     ["AB_PROGNOSE_STATUS","measure_method_arrival"],
#     ["DURCHFAHRT_TF","does_stop_here"]]
#
#
# for de_name, en_name in mapping:
#     real_time = real_time.withColumnRenamed(de_name, en_name)
#     
# print("Final Schema :")
# real_time
# -

# ### Restricting the station to the selected ones where transports arrive

# + language="spark"
# stations = arrivals.select("STOP_NAME").dropDuplicates()
# real_time = real_time.join(stations, "STOP_NAME")
#
# # Compute the delay
# real_time = real_time.withColumn('arrival_time_schedule', 
#                                  unix_timestamp('arrival_time_schedule', "dd.MM.yyyy HH:mm"))\
#                 .withColumn('arrival_time_actual', unix_timestamp('arrival_time_actual', "dd.MM.yyyy HH:mm"))\
#                 .withColumn("arrival_delay", col("arrival_time_actual") - col("arrival_time_schedule"))\
#                 .filter("arrival_delay is not NULL")
#
# # Convert timestamps to day and hour
# real_time = real_time.withColumn("day_of_week", dayofweek(from_unixtime(col("arrival_time_schedule"))))\
#                     .withColumn("hour", hour(from_unixtime(col("arrival_time_schedule"))))
#                     
#
# # Clip negative delays to 0
# real_time = real_time.withColumn("arrival_delay", when(real_time["arrival_delay"] < 0, 0)\
#                                  .when(col("arrival_delay").isNull(), 0)\
#                                  .otherwise(col("arrival_delay")/60)).cache()
# -

# ## EDA of the delay distribution

# + language="spark"
# delays_distrib = real_time.filter("year == 2021").filter("month == 1")\
#                         .select(["STOP_NAME", "produkt_id", "arrival_delay"])\
#                         .groupBy(["STOP_NAME", "produkt_id","arrival_delay"]).count().cache()
#

# + magic_args="-o sample_dist" language="spark"
# sample_dist = delays_distrib.filter(delays_distrib.STOP_NAME ==  "Adliswil")\
#                             .filter(delays_distrib.produkt_id == "Zug")

# +
# Exponential distribution. We are going to fit parameter a
def pdf(x, a):
        return a * np.exp(-a * x)

def plot_delay_dist(sample_dist):
    fig = plt.figure(figsize=(20, 6))
    # Convert frequencies to density
    sample_dist = sample_dist.copy().sort_values("arrival_delay")
    sample_dist['count'] = sample_dist['count'] / sample_dist['count'].sum()
    
    
    g = sns.barplot(data=sample_dist.sort_values("arrival_delay"), x="arrival_delay", y="count")
    g.set_xticklabels(g.get_xticklabels(), rotation=45)
    
    # Fit the exponential
    popt, pcov = curve_fit(pdf, sample_dist.arrival_delay, sample_dist['count'])
    yy = pdf(sample_dist.arrival_delay, *popt)
    g.plot(range(len(sample_dist)), yy, '-o')
    
    station = sample_dist.STOP_NAME.iloc[0]
    transport_mean = sample_dist.produkt_id.iloc[0]
    g.set_xlabel("Delay (min)", fontsize=16)
    g.set_ylabel("Normalized count", fontsize=16)
    g.set_title(f"Delay distribution of trains at {station}", fontsize=16)
    g.text(15, 0.5, f'$\lambda=${popt[0]:.2f}', horizontalalignment='right', verticalalignment='top', fontsize=20)
    plt.show()
    
plot_delay_dist(sample_dist)
# -

# ### Fit distribution on for all (stops, transport type) pairs

# + language="spark"
# from pyspark.sql.functions import pandas_udf, PandasUDFType
# import numpy as np
# from scipy.optimize import curve_fit
#
# @udf
# def compute_lambda_udf(l):
#     counts = np.array(l[1])
#     popt, pcov = curve_fit(lambda x, a: a*np.exp(-a*x), l[0], counts / float(counts.sum()))
#     return float(popt[0])

# + language="spark"
# # Show how it works on a subset
# delays_distrib.withColumn("arrival_delay", col("arrival_delay") /60)\
#                 .groupBy(['STOP_NAME','produkt_id'])\
#                 .agg(struct(collect_list("arrival_delay"), collect_list("count")).alias("delays"))\
#                 .withColumn("lambda", compute_lambda_udf(col("delays"))).show(4)

# + magic_args="-o lambdas " language="spark"
# # This cell takes ~20min
#
# finalCols = ["STOP_NAME", "produkt_id", "day_of_week", "hour"]
#
# # Since we only have the timetable of Wednesday, we only model delays on Wednesday
# # We also restrict the hours of the day from 5am to 10pm
# # Finally we count the frequencey of each delay to create the density function
# day = real_time.select(["STOP_NAME", "produkt_id", "arrival_delay", "day_of_week", "hour"]).dropna()\
#                 .filter(real_time.day_of_week == 3).filter((real_time.hour > 4) & (real_time.hour < 23))\
#                 .groupBy(finalCols + ['arrival_delay']).count()
#
# # From the density of delays we fit an exponential distribution and save the parameter lambda
# lambdas = day.groupBy(finalCols)\
#                 .agg(struct(collect_list("arrival_delay"), collect_list("count")).alias("delays"))\
#                 .withColumn("lambda", compute_lambda_udf(col("delays"))).drop('delays')
# -

lambdas.to_csv('../data.lambdas.csv',index=False)

# # Creating the tables necessary to our graph modelisation

# + language="spark"
#
# from functools import reduce
# from pyspark.sql.functions import col, lit, unix_timestamp, from_unixtime, collect_list
# from pyspark.sql.functions import countDistinct, concat
# from pyspark.sql.functions import udf, explode, split
# import pyspark.sql.functions as F
# from pyspark.sql.types import ArrayType, StringType, IntegerType
# from pyspark.sql.window import Window
# REMOTE_PATH = "/group/abiskop1/project_data/"

# + language="spark"
#
# def count_nan_null(df):
#     df.select([F.count(F.when(F.isnan(c) | col(c).isNull(), c)).alias(c) for c in df.columns]).show()
#
#
# def read_orc(fname):
#     df = spark.read.orc("/data/sbb/part_orc/{name}".format(name=fname))
#     return df.filter((df.year == 2020) & (df.month == 5) & (df.day > 12) & (df.day < 18))
#
#
# def write_hdfs(df, dirname):
#     df.coalesce(1).write.format("com.databricks.spark.csv").mode('overwrite')\
#    .option("header", "true").save(REMOTE_PATH + dirname)

# + language="spark"
# spark.conf.set("spark.sql.session.timeZone", "UTC+2")
# -

# ## Loading selected stations (Stops)

# + language="spark"
#
# stations = spark.read.csv("/data/sbb/csv/allstops/stop_locations.csv")
# oldColumns = stations.schema.names
# newColumns = ["STOP_ID", "STOP_NAME", "STOP_LAT", "STOP_LON", "LOCATION_TYPE", "PARENT_STATION"]
#
# stations = reduce(lambda data, idx: data.withColumnRenamed(oldColumns[idx], newColumns[idx]), xrange(len(oldColumns)), stations)
#
# w = Window.partitionBy('STOP_NAME').orderBy(col("STOP_ID").asc())
# stations = stations.withColumn("row_number",  F.row_number().over(w))\
#                     .withColumn("NEW_STOP_NAME",
#                                F.when(col('row_number') == lit(1), col('STOP_NAME'))
#                                .otherwise(concat(col("STOP_NAME"), lit("_"),  lit(F.row_number().over(w)))))\
#                                 .drop('STOP_NAME').withColumnRenamed('NEW_STOP_NAME', 'STOP_NAME')
# stations.show()
# -
# ## Stops in radius


# + language="spark"
# sel_stops = spark.read.csv("/user/benhaim/final-project/stop_ids_in_radius.csv")
# sel_stops = sel_stops.withColumnRenamed("_c0", "stop_id")
# sel_stops.show(5)
# -
# ## Stop times

# + language="spark"
# stoptimes = spark.read.orc("/data/sbb/part_orc/stop_times")
# stoptimes.printSchema()
# -

# ### Stop times at relevant date

# + language="spark"
# relevant_stoptimes = stoptimes.filter("year == 2020").filter("month == 5").filter("day == 13")
# -

# ### Stop times in radius

# + language="spark"
# close_stoptimes = relevant_stoptimes.join(sel_stops, on="stop_id",how="inner")
#
# close_stoptimes = close_stoptimes.withColumn("arrival_time_complete", \
#                  concat(col("year"), lit("/"), col("month"), lit("/"), col("day"), lit(" "), col("arrival_time")))
# # drop hours above 24
# close_stoptimes = close_stoptimes.withColumn('arrival_time', 
#                                      unix_timestamp('arrival_time_complete', "yyyy/MM/dd HH:mm:ss")).dropna()
# close_stoptimes = close_stoptimes.cache()
# close_stoptimes.printSchema()
# -

# As we can see, in a single day arrival times are duplicated for each stop_id, we will therefore drop them

# + language="spark"
# print(relevant_stoptimes.count())
# relevant_stoptimes.dropDuplicates(['stop_id','arrival_time' ]).count()
# -

# ## Trips

# + language="spark"
# trips = read_orc("trips")
# trips.show()
# -

# ### Checking assumption : pair (trip_id, route_id) is unique

# + language="spark"
# ispairunique = trips.select("route_id", "trip_id")
# print(ispairunique.count() == ispairunique.dropDuplicates().count())
# -

# ### Merging trips and stop_times
# Create clean_stop_seq such that stop sequence are successive

# + language="spark"
# selected_stoptimes = close_stoptimes.select("trip_id", "stop_id", "departure_time", "arrival_time", "stop_sequence")
# trips_stop_times = trips.select("route_id", "trip_id", "trip_headsign").join(selected_stoptimes, on="trip_id",how="inner")
# #trips_stop_times = trips_stop_times.withColumn("route_stop_id", concat(col("route_id"), lit("&"), col("stop_id")))
#
# w = Window.partitionBy(['trip_id']).orderBy(col("stop_sequence").asc())
# trips_stop_times = trips_stop_times.withColumn("clean_stop_seq", F.row_number().over(w))
# trips_stop_times.count()

# + language="spark"
# trips_stop_times.filter(col("clean_stop_seq") !=  col('stop_sequence')).dropDuplicates(["trip_id"]).count()
# -

# Some routes loop over the same stops, therefore we add the occurence index in the stop id for each trip to create
# trip_stop_id and route_stop_id.

# + language="spark"
# w = Window.partitionBy(['trip_id', 'stop_id']).orderBy(col("clean_stop_seq").desc())
# stop_times_ranked = trips_stop_times.withColumn("trip_stop_index", F.row_number().over(w))\
#                         .withColumn("trip_stop_id", concat(col("stop_id"), lit("*"), col("trip_stop_index")))\
#                         .withColumn("route_stop_id", concat(col("route_id"), lit("&"), col("trip_stop_id")))\
#                         .orderBy(['route_stop_id', 'trip_id', 'clean_stop_seq']).cache()
# stop_times_ranked.count()

# + language="spark"
# ispairunique = stop_times_ranked.select("trip_stop_id", "trip_id")
# print(ispairunique.count() == ispairunique.dropDuplicates().count())

# + magic_args="   " language="spark"
# cols = ["route_stop_id", "arrival_time"]
# duplicates = stop_times_ranked.join(
#     stop_times_ranked.groupBy(cols).agg((F.count("*")>1).cast("int").alias("Duplicate_indicator")),
#     on=cols,
#     how="inner"
# ).cache()

# + language="spark"
# duplicates.filter(col("Duplicate_indicator") > 0).count()

# + language="spark"
# routes_orc = read_orc("routes").select('route_id', 'route_desc', 'route_short_name')
#
# duplicates.filter(col("Duplicate_indicator") > 0).join(routes_orc, 'route_id', 'inner')\
#             .join(stations.select('stop_id', 'stop_name'), 'stop_id', 'inner').orderBy(cols).show()
# -

# ### Building time tables
#
# We drop duplicated arrival times for the same (route, stop)

# + language="spark"
# timetable = stop_times_ranked.select(["route_stop_id", "arrival_time"])\
#                     .dropDuplicates(["route_stop_id", "arrival_time"]).cache()

# + language="spark"
# write_hdfs(timetable, "timetableRefacFinal")
# -

# ### Building Route stops

# + language="spark"
#
# window = Window.partitionBy("trip_id").orderBy(col("clean_stop_seq").desc())
#
# max_stop_times = stop_times_ranked.withColumn("row",F.row_number().over(window)) \
#   .filter(col("row") == 1).drop("row").dropDuplicates(["route_id"])
#
# max_stop_times = max_stop_times.select(['trip_id', 'clean_stop_seq'])
# max_stop_times.show(5)
# max_stop_times.count()

# + language="spark"
# max_stop_times.select('clean_stop_seq').groupBy().sum().show()

# + language="spark"
# actual_routes = stop_times_ranked.join(max_stop_times.select('trip_id'), "trip_id", "inner")
# actual_routes.count()

# + language="spark"
# print(actual_routes.count())
# actual_routes.dropDuplicates(['route_stop_id']).count()

# + language="spark"
#
# w = Window.partitionBy("route_id").orderBy(col("clean_stop_seq").desc())
# route_stops = actual_routes.withColumn("actual_stop_seq", F.row_number().over(w)).drop("trip_id", "clean_stop_seq")
# print(actual_routes.count())
# print(route_stops.count())
#
# prevs = route_stops.drop("trip_headsign", "stop_id")\
#                   .withColumnRenamed("actual_stop_seq", "prev_stop_seq")\
#                   .withColumnRenamed("route_stop_id", "prev_route_stop_id")\
#                   .withColumnRenamed("arrival_time", "prev_arrival_time")\
#                   .withColumnRenamed("route_id", "prev_route_id")\
#                     .select(['prev_stop_seq', 'prev_route_stop_id', 
#                              'prev_arrival_time', 'prev_route_id'])
#
# route_stops = route_stops.withColumn("matching_stop_seq", col("actual_stop_seq") + 1)
#
#
# route_stops = route_stops.join(prevs, (prevs.prev_stop_seq == route_stops.matching_stop_seq) \
#                                       & (prevs.prev_route_id == route_stops.route_id), "leftouter").cache()
#
# print(route_stops.count())

# + language="spark"
# complete_route_stops = route_stops.withColumn("travel_time", col("arrival_time") - col("prev_arrival_time"))\
#                         .drop("prev_stop_seq", "prev_arrival_time", "arrival_time",
#                               'matching_stop_seq', 'prev_route_id', 'clean_stop_seq')\
#                         .cache()
# complete_route_stops.show(5)

# + language="spark"
# routes_orc = read_orc("routes").select('route_id', 'route_desc', 'route_short_name')
# final_complete_route_stops = complete_route_stops.join(routes_orc, 'route_id', 'inner')\
#                                                 .drop('route_id')\
#                                                 .join(stations.select('stop_id', 'stop_name'), 'stop_id', 'inner')
#
# final_complete_route_stops.select('route_desc').show(5)

# + language="spark"
# print(final_complete_route_stops.count())
# print(complete_route_stops.count())

# + language="spark"
# count_nan_null(final_complete_route_stops)

# + language="spark"
# write_hdfs(final_complete_route_stops, "routestops")
# -

# # Stations

# + language="spark"
# final_stations = final_complete_route_stops.groupby('stop_id')\
#                 .agg(F.collect_list(col('route_stop_id')).alias('route_stops'))\
#                 .join(stations, 'stop_id', 'inner').drop('location_type', 'parent_station').cache()
# final_stations.show(5, False)
# + magic_args="-o  final_stations" language="spark"
# final_stations.count()
# -

final_stations.to_csv('../data/stations.csv', index=False)
