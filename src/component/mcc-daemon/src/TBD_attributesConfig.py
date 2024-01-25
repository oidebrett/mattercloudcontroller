#
# Copyright (c) 2023 Matter Cloud Controller Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import chip.clusters as Clusters

###########################################################################
#
# This file helps set the attributes that are returned to the matter shadow
#
###########################################################################

'''
#if we all of everything in the node we could just ask for these
AttributesInScope = ['*']

#if we all of endpoint 0 we could just ask for these
AttributesInScope = [0]

#if we are limited to json document size we could just ask for these
AttributesInScope = [
    (0, Clusters.BasicInformation),
    (0, Clusters.GeneralDiagnostics),
    (0, Clusters.AccessControl)
    ]
'''

#if we are less limited to json document size we could just ask for these
AttributesInScope = [
    (0, Clusters.BasicInformation),
    (0, Clusters.Identify),
    (0, Clusters.GeneralDiagnostics),
    (0, Clusters.Groups),
    (0, Clusters.Descriptor),
    (0, Clusters.Binding),
    (0, Clusters.AccessControl),
    (0, Clusters.OtaSoftwareUpdateRequestor),
#            (0, Clusters.LocalizationConfiguration),
#            (0, Clusters.TimeFormatLocalization),
#            (0, Clusters.UnitLocalization),
    (0, Clusters.PowerSourceConfiguration),
    (0, Clusters.PowerSource),
    (0, Clusters.GeneralCommissioning),
    (0, Clusters.NetworkCommissioning),
    (0, Clusters.DiagnosticLogs),
    (0, Clusters.SoftwareDiagnostics),
    (0, Clusters.ThreadNetworkDiagnostics),
    (0, Clusters.WiFiNetworkDiagnostics),
    (0, Clusters.EthernetNetworkDiagnostics),
    (0, Clusters.AdministratorCommissioning),
    (0, Clusters.OperationalCredentials),
    (0, Clusters.GroupKeyManagement),
    (0, Clusters.FixedLabel),
    (0, Clusters.UserLabel),
    (0, Clusters.RelativeHumidityMeasurement),
    (0, Clusters.IcdManagement),
    (0, Clusters.FaultInjection)
    ]

'''

#if we are limited to json document size we could just ask for these specific attributes
large_read_contents = [
    Clusters.BasicInformation.Attributes.DataModelRevision,
    Clusters.BasicInformation.Attributes.VendorName,
    Clusters.BasicInformation.Attributes.VendorID,
    Clusters.BasicInformation.Attributes.ProductName,
    Clusters.BasicInformation.Attributes.ProductID,
    Clusters.BasicInformation.Attributes.NodeLabel,
    Clusters.BasicInformation.Attributes.Location,
    Clusters.BasicInformation.Attributes.HardwareVersion,
    Clusters.BasicInformation.Attributes.HardwareVersionString,
]
AttributesInScope = [(0, attrib) for attrib in large_read_contents]
'''