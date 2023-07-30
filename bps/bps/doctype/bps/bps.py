import frappe
from frappe.model.document import Document
from datetime import datetime
import requests
import json
import os
import re
from base64 import b64encode
import pandas as pd


class BPS(Document):
    details_dict = {}
    patient_id = None
    file_name = ""

    def get_json_response(self, url):
        if self.authentication_key == "****" or self.authentication_key == "":
            frappe.throw("Authentication key is missing or invalid.")

        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + self.authentication_key,
        }
        response = requests.get(url, headers=headers)

        return (response.status_code, response.json())

    def send_post_request(self, url):
        return requests.post(url)

    def encode(self, name, value, operator=None):
        if operator == "or":
            return "%2C" + name + "%3D%3D" + value
        elif operator == "and":
            return "%3B" + name + "%3D%3D" + value

        return name + "%3D%3D" + value

    def _or(self, name, value):
        return self.encode(name, value, "or")

    def _and(self, name, value):
        return self.encode(name, value, "and")

    def replace_url_patient_id(self, url, patient_id):
        return url.replace("{patient_id}", patient_id)

    def get_patient_addresses(self, patient_id):
        try:
            responce_status, patient_addresses_responce = self.get_json_response(
                self.replace_url_patient_id(self.demographics, patient_id)
            )

            if responce_status != 200:
                frappe.throw("Error: Invalid API Request/Response (address)")

            # elif not self.validate_post_code(patient_addresses_responce):
            #     frappe.throw("Post Code does not match")

            return patient_addresses_responce[0]

        except Exception as e:
            print("Error: ", e)

    def get_file_data(self, url):
        data_response = requests.get(url)
        file_format = data_response.headers["Content-Type"].split("/")[-1].upper()
        return str(data_response.content), file_format

    def process_inner_urls(self, _response):
        count = 1
        for response in _response["data"]:
            response["recordStatus"] = 1
            response["id"] = count
            count += 1

            if response["attachmentUrl"] != None:
                (
                    response["attachmentContent"],
                    response["documentType"],
                ) = self.get_file_data(response["attachmentUrl"])

            else:
                if "htmlContent" in response.keys():
                    if response["htmlContent"] != None:
                        response["documentType"] = "HTML"
                        html_bytes = response["htmlContent"]
                        response["attachmentContent"] = html_bytes

        return _response

    def get_patient_correspondenceIn(self, patient_id):
        try:
            responce_status, patient_correspondenceIn_response = self.get_json_response(
                self.replace_url_patient_id(self.correspondence_in, patient_id)
            )

            if responce_status != 200:
                frappe.throw("Error: Invalid API Request/Response (corrIn)")

            patient_correspondenceIn_response = self.process_inner_urls(
                patient_correspondenceIn_response
            )

            return patient_correspondenceIn_response["data"]

        except Exception as e:
            print("Error: ", e)

    def get_patient_correspondenceOut(self, patient_id):
        try:
            (
                responce_status,
                patient_correspondenceOut_response,
            ) = self.get_json_response(
                self.replace_url_patient_id(self.correspondence_out, patient_id)
            )

            if responce_status != 200:
                frappe.throw("Error: Invalid API Request/Response (corr Out)")

            patient_correspondenceOut_response = self.process_inner_urls(
                patient_correspondenceOut_response
            )

            return patient_correspondenceOut_response["data"]

        except Exception as e:
            print("Error: ", e)

    def get_patient_settings(self, patient_id):
        try:
            responce_status, patient_settings_response = self.get_json_response(
                self.replace_url_patient_id(self.patient_settings, patient_id)
            )

            if responce_status != 200:
                frappe.throw("Error: Invalid API response/request (Settings)")
                return None

            return patient_settings_response

        except Exception as e:
            print("Error: ", e)

    # practice concept
    def get_practice_details(self, defaultPractice):
        try:
            responce_status, practice_details_response = self.get_json_response(
                self.practice_details + defaultPractice
            )

            if responce_status != 200:
                frappe.throw("Error: Invalid API Request/Response (practice)")

            else:
                if (
                    practice_details_response["practiceName"]
                    == "Vecare Health Holbrook"
                ):
                    practice_details_response["practiceId"] = "24784"

                elif (
                    practice_details_response["practiceName"]
                    == "Vecare Health - Walla Walla"
                ):
                    practice_details_response["practiceId"] = "28200"

            return practice_details_response

        except Exception as e:
            print("Error: ", e)

    def process_json(self):
        try:
            if self.full_name != None and self.full_name != "":
                if (self.first_name == None or self.first_name == "") or (
                    self.last_name == None or self.last_name == ""
                ):
                    self.first_name = self.full_name.split(",")[1].strip()
                    self.last_name = self.full_name.split(",")[0]

            else:
                self.full_name = self.last_name + "," + self.first_name

            print(pd.to_datetime(self.date_of_birth).date())
            response_status, patient_search_response = self.get_json_response(
                self.search_endpoint
                + "?q="
                + self.encode("firstName", self.first_name)
                + self._and("lastName", self.last_name)
                + self._and("dob", str(pd.to_datetime(self.date_of_birth).date()))
            )

            if response_status != 200:
                frappe.throw("Error: Invalid API Request/Response (search)")

            elif len(patient_search_response["data"]) == 0:
                frappe.throw("No Record Found!")

            else:
                self.patient_id = patient_search_response["data"][0]["id"]
                self.patient_id = patient_search_response["data"][0]["id"]

                self.patient_id = patient_search_response["data"][0]["id"]

                if (len(patient_search_response["data"][0]) != 0) and (
                    self.patient_id != None
                ):
                    patient_search_response["data"][0]["recordStatus"] = 1
                    patient_search_response["data"][0]["patientStatus"] = 1

                    self.details_dict["patientDetails"] = patient_search_response[
                        "data"
                    ][0]
                    self.details_dict["patientSettings"] = self.get_patient_settings(
                        self.patient_id
                    )

                    self.details_dict["patientAddress"] = self.get_patient_addresses(
                        self.patient_id
                    )

                    if self.details_dict["patientAddress"] is not None:
                        self.details_dict[
                            "correspondenceInbound"
                        ] = self.get_patient_correspondenceIn(self.patient_id)
                        self.details_dict[
                            "correspondenceOutbound"
                        ] = self.get_patient_correspondenceOut(self.patient_id)

                        self.details_dict["practice"] = self.get_practice_details(
                            self.details_dict["patientDetails"]["defaultPracticeId"]
                        )
                        
                else:
                    frappe.throw("Could not find patient!")
                    # print("details_dictionary is ready")

                self.file_name = (
                    self.first_name
                    + "_"
                    + self.last_name
                    + "_"
                    + self.details_dict["practice"]["practiceName"]
                )
                with open(
                    f"/home/frappe/frappe-bench/sites/json/{self.file_name}.json", "w"
                ) as outfile:
                    json.dump([self.details_dict], outfile)

        except Exception as e:
            print("Error:", e)

    def clear_credientials(self):
        self.authentication_key = "****"

    def save_xml_doc(self):
        if os.path.exists(f"/home/frappe/frappe-bench/sites/xml/{self.file_name}.xml"):
            with open(
                f"/home/frappe/frappe-bench/sites/xml/{self.file_name}.xml", "rb"
            ) as file:
                file_doc = frappe.get_doc(
                    {
                        "doctype": "File",
                        "file_name": self.file_name + ".xml",
                        "folder": "Home/BPS",
                        "content": file.read(),
                    }
                )
                file_doc.save()

    def clear_files(self):
        # check the file exists
        # if os.path.exists(
        #     f"/home/frappe/frappe-bench/sites/json/{self.file_name}.json"
        # ):
        #     os.remove(f"/home/frappe/frappe-bench/sites/json/{self.file_name}.json")

        # if os.path.exists(f"/home/frappe/frappe-bench/sites/xml/{self.file_name}.xml"):
        #     os.remove(f"/home/frappe/frappe-bench/sites/xml/{self.file_name}.xml")

    def validate(self):
        # checking only the post code!
        # if not self.post_code.isdigit():
        #     frappe.throw("Invalid Post Code!")
        self.process_json()
        if self.file_name is not "":
            self.send_post_request(
                f"http://172.19.0.1:8080/ehr/api/v1/launch?patient_file={self.file_name}.json&output_file={self.file_name}.xml"
        )
        else:
            frappe.throw("Invalid File Name!")
        
        # self.save_xml_doc()
        self.clear_credientials()
        #self.clear_files()
