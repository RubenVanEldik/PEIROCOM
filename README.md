## PEIROCOM

The Pan-European Intermittent Renewable Overbuilding and Curtailment Optimization Model (PEIROCOM) is an optimization model for a fully intermittent renewable Pan-European electricity grid. The model aims to find the least-cost solution for the deployment of solar PV, wind energy and storage. By overbuilding generation capacity to some degree, significant less storage capacity is required, resulting in lower system costs.

The demand and climate data used in this model are from ENTSO-E's 2021 European Resource Adequacy Assessment (ERAA) and can be downloaded [here](https://www.entsoe.eu/outlooks/eraa/2021/eraa-downloads/). The techno-economic data is from NREL's Annual Technology Baseline and can be found [here](https://atb.nrel.gov/).

The source code of the model can be found on [Github](https://github.com/RubenVanEldik/thesis-model). It consists out of three parts, the preprocessing, optimization, and analysis.

### Variability
The variability page is not part of the model, but is a quick tool to create a plot with the daily/yearly variability of demand and IRES production.

### Preprocessing
The preprocessor only needs to be run once. It converts the hourly ERAA data in Excel to a single CSV file per bidding zone. These CSV files are tailor made to improve the initialization of the model.

### Optimization
...

### Analysis
The model returns up to multiple GB's of data. To quickly and effectivily analyse the results of a given run, there are six analysis tools that can be used to parse and analyze the results.

###### Statistics
The statistics analysis shows an executive summary of the results, including the LCOE, firm kWh premium, and relative curtailment, as well as the production and storage capacities.

###### Temporal results
The temporal results analysis simply shows a temporal plot for the given columns within a certain date range.

###### Countries
The countries analysis projects the value of a given indicator on a European map.

###### Correlation
The correlation analysis shows the correlation between the distance of two countries and the temporal values of a given column.

###### Duration Curve
The duration curve analysis shows the (relative) duration curve of a given column.

###### Sensitivity
The sensitivity analysis is only available for runs with a sensitivity analysis enabled and shows the results of this analysis.

###### Optimization log
The optimization log is not an analysis, but merely shows the Gurobi optimization log for a specific run and resolution.
