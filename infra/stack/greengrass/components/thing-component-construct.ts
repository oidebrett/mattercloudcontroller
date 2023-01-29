import * as cdk from '@aws-cdk/core';
import * as s3 from '@aws-cdk/aws-s3';
import * as gg2 from '@aws-cdk/aws-greengrassv2';

import * as base from '../../../../lib/template/construct/base/base-construct';

export interface ConstructProps extends base.ConstructCommonProps {
    bucket: s3.IBucket;
    compConfig: any;
    components: any;
}

export class ThingComponent extends base.BaseConstruct {
    private compName: string;

    constructor(scope: cdk.Construct, id: string, props: ConstructProps) {
        super(scope, id, props);

        this.compName = `${this.projectPrefix}-${props.compConfig['Name']}`;
        
        const iotRuleTopic = this.parseRuleTopic();

        const receipe: any = this.createRecipe(props.bucket, props.compConfig, iotRuleTopic);

        const ggComponent = new gg2.CfnComponentVersion(this, `${this.compName}Comp`, {
            inlineRecipe: JSON.stringify(receipe)
        });

        this.addAccessControl(props.components, ggComponent, iotRuleTopic);
    }

    private parseRuleTopic(): string {
//        const ruleNameSuffix = this.commonProps.appConfig.Stack.DataPipeline.IoTRuleNameFirehoseIngestion;
        const ruleNameSuffix = "rule";
        const ruleName = `${this.projectPrefix}_${ruleNameSuffix}`.toLowerCase().replace('-', '_');
//        const topicPrefix = this.commonProps.appConfig.Stack.DataPipeline.IoTRuleTopic;
        const topicPrefix = "topic";
        const topic = `${topicPrefix}/${ruleName}`;

        return topic;
    }

    private createRecipe(bucket: s3.IBucket, compConfig: any, ruleTopic: string): any {
        const compVersion = compConfig['Version'];
        const compArgs = compConfig['Args'];
        const bucketKey = this.commonProps.appConfig.Stack.ComponentUpload.BucketPrefix;

        const recipe: any = {
            "RecipeFormatVersion": "2020-01-25",
            "ComponentName": this.compName,
            "ComponentVersion": compVersion,
            "ComponentDescription": `This component's name is ${this.compName}`,
            "ComponentPublisher": "oide",
            "ComponentConfiguration": {
                "DefaultConfiguration": {
                    "accessControl": {
                        "aws.greengrass.ShadowManager": {
                            "thing:shadow:1": {
                            "policyDescription": "Allows access to shadows",
                            "operations": [
                              "aws.greengrass#GetThingShadow",
                              "aws.greengrass#UpdateThingShadow",
                              "aws.greengrass#DeleteThingShadow",
                              "aws.greengrass#SubscribeToTopic"
                            ],
                            "resources": [
                              "*"
                            ]
                          },
                          "thing:shadow:2": {
                            "policyDescription": "Allows access to things with shadows",
                            "operations": [
                              "aws.greengrass#ListNamedShadowsForThing"
                            ],
                            "resources": [
                              "*"
                            ]
                          }    
                        }
                      }  
                }
            },
            "Manifests": [
                {
                    "Platform": {
                        "os": "linux"
                    },
                    "Lifecycle": {
                        "Setenv": {
                            "COMP_NAME_VERION": `${this.compName}:${compVersion}`,
                            "RULE_TOPIC": ruleTopic,
                            "SLEEP_TIME": '22',
                            "FUNCTION_VERION": `${this.compName}:${compVersion}`,
                        },
                        "Install": {
                            "script": `. /home/ubuntu/connectedhomeip/out/python_env/bin/activate\npip3 install -r {artifacts:decompressedPath}/${this.compName}/requirements.txt`
                        },
                        "Run": {
                            "script": `. /home/ubuntu/connectedhomeip/out/python_env/bin/activate\npython3 {artifacts:decompressedPath}/${this.compName}/iotMatterCloudController.py ${compArgs}\n`
                        },
                    },
                    "Artifacts": [
                        {
                            "URI": `s3://${bucket.bucketName}/${bucketKey}/${this.compName}/${compVersion}/${this.compName}.zip`,
                            "Unarchive": "ZIP"
                        }
                    ]
                }
            ]
        };

        return recipe;
    }

    private addAccessControl(components: any, ggComponent: gg2.CfnComponentVersion, iotRuleTopic: string) {
//        const topicWild = `${iotRuleTopic}/#`;
        const topicWild = `#`;

        components[this.compName] = {
            componentVersion: ggComponent.attrComponentVersion,
            configurationUpdate: {
                merge: JSON.stringify({
                    "accessControl": {
                        "aws.greengrass.ipc.mqttproxy": {
                            "thing:mqttproxy:1": {
                                "policyDescription": "Allows access to subscribe and publish to IoTCore",
                                "operations": [
                                    "aws.greengrass#PublishToIoTCore",
                                    "aws.greengrass#SubscribeToIoTCore",
                                    "aws.greengrass#SubscribeTopic",
                                    "aws.greengrass#SubscribeToTopic"
                                ],
                                "resources": [
                                    topicWild
                                ]
                            }
                        },
                        "aws.greengrass.ipc.pubsub": {
                            "thing:pubsub:1": {
                              "policyDescription": "Allows access to publish/subscribe to all topics.",
                              "operations": [
                                "aws.greengrass#PublishToTopic",
                                "aws.greengrass#SubscribeToTopic"
                              ],
                              "resources": [
                                "*"
                              ]
                            }
                          }
                    }
                })
            }
        };
    }
}