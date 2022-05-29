# Data Retrieval Service

## SI3D Model
To predict hazardous conditions in Lake Tahoe, we use a program written in Fortran called the `si3d` model. It takes in various conditions as input such as air temperature, air pressure, and wind speed, and it outputs a forecast for several properties of the lake over a time period.

## Data Retrieval Service
This repository hosts Python scripts that automates the workflow of the si3d model. The main Python script `si3d.py` performs the following tasks:
1. Retrieve the necessary data from various API's
2. Generate input files for the si3d program
3. Run the compiled si3d binary

The steps for installation may be skipped for the Amazon EC2 instance that we use, as this repository has already been setup there. 

Table of Contents
1. [Installation](#installation)
2. [Running the model](#running-the-model)
3. [Updating this repository](#updating-this-repository)
4. [Known errors](#known-errors)
5. [Technical details](#technical-details)

## Installation on EC2 instance
### Configuring an EC2 instance
1. Create an EC2 instance. This is meant to be persistent, so do not terminate the instance!
2. Run `aws configure` and add your AWS account credentials. Our code uses the `aws` command line tool to shutdown the EC2 instance.

### Prerequisites
Install these packages in the EC2 instance if they don't already exist:
- Python 3 (any 3.x version should work, but we use 3.8.10 in our EC2 instance)
- Pip

### Setting up repository
1. Begin by cloning this repository with:
`git clone https://github.com/ECS-193A-Red-Phoenix/LakeTahoe-HazardWarningSystem.git`
2. Install the dependencies using:
`pip install -r requirements.txt`
3. Copy `drs.service` into the `/etc/systemd/system` folder. This config file tells the system to start the data retrieval service when the instance boots up.
`sudo cp drs.service /etc/systemd/system``

## Running the model
To start the si3d workflow, run the following:

`python3 si3d.py`

Running this command will complete the following steps:

1. Retrieve data, clean it, and prepare model input files located in `model/psi3d`. In particular, we update `surfbc.txt`, `si3d_inp.txt`, and `si3d_init.txt`. These input files are all located within the `model/psi3d`.
2. Run the si3d executable `model/psi3d/psi3d`
3. Parse the model output file `model/psi3d/plane_2` and generate `.npy` files for each temperature and flow visualization in `outputs`
4. Upload the `.npy` files to S3 and update `contents.json`, deleting old `.npy` files in our S3 bucket and locally if any.
5. Shutdown the EC2 instance.

## Updating this repository

To push new changes to this repository, make commits locally and push to the main branch on github using

`git push origin main`

Afterwards, log onto the EC2 instance and pull these changes using

`git pull origin main`

Note: The above step may result in an error due to unsaved local files on the EC2 instance. In this case, you may disgard these local changes using `git restore .`

## Known Errors

Running `si3d.py` may crash and return an error for the following documented reasons.

1. A critical API endpoint may be down. This means that we are missing critical information for an accurate model run. 

## Technical Details

This section will describe some of the methodology and organization of our code.  

### What is surfbc.txt and how is it automatically updated?

One of crucial si3d input files is `surfbc.txt`. This is the layout of the file:
- The first 6 lines of this file are informational headers that are ignored by si3d when it is parsed.
- The 7th line describes how many data points are listed below.
- The rest of the file consists of 10 columns of data that the model uses to simulate the lake. The columns are 10 characters long, right aligned, and each is separated with space character. The 10 columns represent the following:
    - time
    - attenuation coefficient
    - shortwave
    - air temp
    - atmospheric pressure
    - relative humidity
    - longwave
    - wind drag coefficient
    - wind u
    - wind v

The attenuation coefficient and wind drag coefficients are predefined constants. To create the `surfbc.txt` file, we must retrieve past and future data for each of these variables and concatenate the two. Typically, we retrieve data starting from one week from the present date and ending for as far as the forecasts go (typically up to a week in the future).

To retrieve past data, we collect JSON samples from USCG and NASA Buoy API's. This data is processed into a dataframe and cleaned using different statistical techniques to eliminate noise. The code for this is located in `get_model_historical_data` in `dataretrieval/aws.py`.

To retrieve future data, we collect JSON samples from the [National Weather Service (NWS) API](https://www.weather.gov/documentation/services-web-api). However, NWS only provides the following data: wind direction, wind speed, air temperature, sky cover, and relative humidity. Thus, we had to find a way to predict atmospheric pressure, longwave, and shortwave. We predict atmospheric pressure using the barometric pressure equation. Longwave is predicted as a function of air temperature and cloud cover. Shortwave is predicted as a function of time. Future data from the NWS contains relatively no noise so we do not perform statistical cleaning. The code for this is located in `get_model_forecast_data` in `dataretrieval/nws.py`

The code that combines past and future data and creates `surfbc.txt` is located in `dataretrieval/service.py`.

<br/>

### What is si3d_inp.txt and how is it automatically updated?

`si3d_inp.txt` is a text file that lists various hyperparameters and meta data used by si3d. To ensure that the model output files are properly dated, one must change the simulation start date in `si3d_inp.txt`. We update this date everytime the simulation is run. 

The code that updates `si3d_inp.txt` is located in `model/update_si3d_inp.py`.

<br/>

### What is si3d_init.txt and how is it automatically updated?

When the simulation begins, si3d requires an initial temperature profile of the lake. This temperature profile is described within `si3d_init.txt`. Typically, the data within `si3d_init.txt` is gathered from a CTD, processed and formatted, and manually entered. Since this is a manual process that is not available to use via an API (not yet at least), we use data from the most recent si3d simulation to create this file. After every simulation, si3d extracts data at various grid cells (dx, dy) and writes them into a text file named `tf<dx>_<dy>.txt`. We process this tf file and extract the temperature profile of the lake at the desired time to create a new `si3d_init.txt`. Currently, we use the node located at 65, 135 for this (Note: this for a bathymetry file with a cell size of 200m).

The code that updates `si3d_init.txt` is located in `model/update_si3d_init.py`.

<br/>

### What data does the model output and how is it formatted?

The model generates two output files, `ptrack_hydro.bnr` and `plane_2`. The first file, `ptrack_hydro.bnr`, contains 3D data of the lake at each time step. This file is ignored and not used. The second file, `plane_2`, contains temperature and water current data at the surface of the lake at each time step. `plane_2` is a binary file with a bespoke file format. The code to read this file is located in `model/HPlane_Si3DtoPython.py`. 

We read `plane_2` and output a dated `.npy` file within the `outputs/` directory. A `.npy` file can be loaded in NumPy. In `outputs/temperature` each `.npy` file contains a 2D NumPy array where each cell in the array is the temperature of lake at the given grid cell. Similarly, in `outputs/flow` each `.npy` file contains 2 NumPy arrays, one for each of the u and v components of water currents. The code that creates `.npy` files is located in `model/create_output_binary.py`.

<br/>

### How are model output files managed?

After every simulation, we upload recent `.npy` files to S3. Afterwards, we delete files in S3 that are older than two weeks. S3 also contains a file `contents.json` that lists the available `.npy` files. This is necessary for our website to know which files are available in S3. 

<br/>



