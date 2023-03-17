# PEIROCOM

**V0.1.16**

The Pan-European Intermittent Renewable Overbuilding and Curtailment Optimization Model (PEIROCOM) is an optimization model for a fully intermittent renewable Pan-European electricity grid. The model aims to find the least-cost solution for the deployment of solar PV, wind energy and storage. By overbuilding generation capacity to some degree, significant less storage capacity is required, resulting in lower system costs.

The demand, IRES, hydropower, and interconnection capacity data are from ENTSO-E's [2021 European Resource Adequacy Assessment (ERAA)](https://www.entsoe.eu/outlooks/eraa/2021/eraa-downloads/). The techno-economic data is from NREL's [Annual Technology Baseline](https://atb.nrel.gov/).

The source code of the model is hosted on [GitHub](https://github.com/RubenVanEldik/PEIROCOM).

## Getting started

After copying `.env.example` to `.env` and adding the specified environment variables. The app can be started using these commands.

```shell
pip install -r requirements.txt
streamlit run 🌤️_Introduction.py
```

This will install the required packages and start up the Streamlit app.

## Deploying

PEIROCOM can be deployed on a (HPC) server in just four steps. After downloading the repository and adding the environment variables in `.env`, Docker can be installed and the server can be spun up using the following commands:

```shell
bash scripts/install_docker.sh
bash scripts/run.sh
```

## Features

PEIROCOM consists out of three sections, preprocessing, optimization, and analysis.

### Preprocessing

The preprocessor only needs to be run once. It removes some irregularities and converts the hourly ERAA data in Excel to a single CSV file per market node.

### Optimization

The optimization is the core of PEIROCOM. All input parameters are dynamically defined, this makes it possible to select the countries and climate years that should be included in a specific run.

### Analysis

After a model is finished it stores all data on the disk. To quickly and effectively analyze the results of a given run, there are various analysis tools that can be used to parse and analyze the results.

## Licensing

The code in this project is licensed under MIT license and can be found [here](https://github.com/RubenVanEldik/PEIROCOM/blob/main/LICENSE).
