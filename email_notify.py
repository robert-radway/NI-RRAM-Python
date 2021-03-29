import yagmail
import argparse

sender = "ni.rram.status@gmail.com"
pw = "allen128x"
receiver = "lihaitong.pku@gmail.com"
message = "NI-RRAM Status: Testing Finished."

parser = argparse.ArgumentParser(description="pass a message")
parser.add_argument('-m', "--message", default=message, help='Pass a message to specify the measurement.')
args = parser.parse_args()

yag = yagmail.SMTP(sender, pw)
yag.send(
    to=receiver,
    subject="NI-RRAM Status: Testing Finished.",
    contents=args.message
)