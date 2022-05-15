"""
Running this script will regularly perform this sequence of tasks

1. Fetch data from AWS + NWS and store them in the database
2. Create input surfbc.txt file
3. Run the model
4. Generate output images
"""

from dataretrieval.service import DataRetrievalService
from model.run_model import run_si3d
from model.create_output_binary import create_output_binary
from model.update_si3d_inp import update_si3d_inp
from save_model_output import save_model_output
import datetime
import os

MODEL_DIR = "./model/psi3d/"
format_date = lambda date: datetime.datetime.strftime(date, "%Y-%m-%d %H:%M:%S UTC")
format_duration = lambda delta: str(delta)

drs = DataRetrievalService()

def run_si3d_workflow():
    start = datetime.datetime.now(datetime.timezone.utc)
    print(f"[DataRetrievalService]: Starting si3d workflow at {format_date(start)}")

    model_start_date = start - datetime.timedelta(weeks=1)

    try:
        # Retrieve data from various API's
        drs.retrieve()
        drs.create_si3d_surfbc(f"{MODEL_DIR}/surfbc.txt", model_start_date)

        # Update si3d_inp.txt
        update_si3d_inp(model_start_date)

        # Run si3d model
        run_si3d()

        # Parse model output into Numpy array files
        create_output_binary()

        # Send array files to S3
        save_model_output()

        end = datetime.datetime.now(datetime.timezone.utc)
        print(f"[DataRetrievalService]: Finished si3d workflow at {format_date(end)}")
        print(f"[DataRetrievalService]: Job 'si3d workflow' took {format_duration(end - start)} to complete")
    except Exception as e:
        print(f"[DataRetrievalService]: DRS failed due to error")
        print(e)
    finally:
        # Shutdown EC2 instance
        # https://stackoverflow.com/a/22913651
        # Must invoke IMDSv2 to get current instance ID for shutting down
        os.system("aws ec2 stop-instances --instance-ids $(curl -s http://169.254.169.254/latest/meta-data/instance-id)")

if __name__ == '__main__':
    run_si3d_workflow()