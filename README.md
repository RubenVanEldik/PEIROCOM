# PEIROCOM

**V0.1.3**

The Pan-European Intermittent Renewable Overbuilding and Curtailment Optimization Model (PEIROCOM) is an optimization model for a fully intermittent renewable Pan-European electricity grid. The model aims to find the least-cost solution for the deployment of solar PV, wind energy and storage. By overbuilding generation capacity to some degree, significant less storage capacity is required, resulting in lower system costs.

The demand, climate, and interconnection capacity data are from ENTSO-E's 2021 European Resource Adequacy Assessment (ERAA) and can be downloaded [here](https://www.entsoe.eu/outlooks/eraa/2021/eraa-downloads/). The techno-economic data is from NREL's Annual Technology Baseline and can be found [here](https://atb.nrel.gov/).

The source code of the model can be found on [Github](https://github.com/RubenVanEldik/PEIROCOM).

## Getting started

After copying `.env.example` to `.env` and adding the specified environment variables. The app can be started using using these commands.

```shell
pip install -r requirements.txt
streamlit run 🌤️_Introduction.py
```

This will install the required packages and start up the Streamlit app.


## Deploying

To deploy the app on a (HPC) server the the app can be exported using the commands below. These will package and upload the Docker container to the specified server.

```shell
cd scripts
bash docker.build.sh
bash docker.export.sh
bash docker.upload.sh
```

On the server side the package can be imported and run as follows.

```shell
cd scripts
bash docker.import.sh
bash docker.run.sh
```

## Features

PEIROCOM consists out of three sections, preprocessing, optimization, and analysis.

### Variability

The variability page is not part of the model, but is a quick tool to create a plot with the daily/yearly variability of demand and IRES production. The data is imported via the ENTSO-E Transparency API.

### Preprocessing

The preprocessor only needs to be run once. It converts the hourly ERAA data in Excel to a single CSV file per bidding zone.
These CSV files are designed to enhance the model's initialization time.

### Optimization

The optimization is the core of PEIROCOM. All input parameters are dynamically defined, this makes it possible to select the countries and climate years that should be included in a specific run. The model uses the time-hierarchical solution method (THS) to improve the optimization time.

### Analysis

The model returns up to multiple GB's of data. To quickly and effectivily analyse the results of a given run, there are six analysis tools that can be used to parse and analyze the results.


## Licensing

The code in this project is licensed under MIT license and can be found [here](https://github.com/RubenVanEldik/PEIROCOM/blob/main/LICENSE).
