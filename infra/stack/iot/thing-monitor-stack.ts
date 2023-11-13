import * as cdk from '@aws-cdk/core';
import * as iot from '@aws-cdk/aws-iot';
import * as iam from '@aws-cdk/aws-iam';
import * as lambda from '@aws-cdk/aws-lambda';
import * as cr from '@aws-cdk/custom-resources';
import * as sns from '@aws-cdk/aws-sns';
import * as subscriptions from '@aws-cdk/aws-sns-subscriptions'

import * as base from '../../../lib/template/stack/base/base-stack';
import { AppContext } from '../../../lib/template/app-context';

export class ThingMonitorStack extends base.BaseStack {

    constructor(appContext: AppContext, stackConfig: any) {
        super(appContext, stackConfig);

        const ruleList: any[] = [
//            { name: 'thing_created', topic: 'created', sns_topic: 'node_created' },
            { name: 'thing_updated', topic: 'update/accepted', sns_topic: 'node_updated_topic_test' },
            { name: 'thing_deleted', topic: 'deleted', sns_topic: 'node_deleted_topic_test' },
        ];

        ruleList.forEach((rule) => { this.createIotRule(rule.name, rule.topic, rule.sns_topic) });
    }

    // https://docs.aws.amazon.com/iot/latest/developerguide/registry-events.html
    private createIotRule(ruleName: string, topic: string, sns_topic: string) {
        const sql = `SELECT topic(3) as thing_name, topic(6) as shadow_name, state.reported as reported FROM '$aws/things/+/shadow/name/+/${topic}'`;

        const role = new iam.Role(this, `${ruleName}Role`, {
            roleName: `${this.projectPrefix}-${ruleName}Role`,
            assumedBy: new iam.ServicePrincipal('iot.amazonaws.com'),
        });

        const SnsTopic = new sns.Topic(this, sns_topic);

        role.addToPolicy(
            new iam.PolicyStatement({
                resources: [SnsTopic.topicArn],
                actions: [
                    "sns:Publish",
                    "sns:CreateTopic",
                    "sns:AddSubscription",
                    "sns:GetTopicAttributes",
                    "sns:Subscribe" 
                ]
            })
        );

        SnsTopic.addSubscription(new subscriptions.LambdaSubscription(new lambda.Function(this, `iot-update-db-${ruleName}`, {
            functionName: `${this.projectPrefix}-iot-update-db-${ruleName}Function`,
            code: lambda.Code.fromAsset('./src/lambda/custom_iot_update_db/src/gg-iot-update-db.zip'),
            handler: 'handler.lambda_handler',
            timeout: cdk.Duration.seconds(120),
            runtime: lambda.Runtime.PYTHON_3_9,
        })));

        new iot.CfnTopicRule(this, ruleName, {
            ruleName: `${this.projectPrefix.toLowerCase().replace('-', '_')}_${ruleName}`,
            topicRulePayload: {
                ruleDisabled: false,
                sql: sql,
                awsIotSqlVersion: '2016-03-23',
                actions: [{ sns: { targetArn: SnsTopic.topicArn, roleArn: role.roleArn } }]
            }
        });
    }
}

