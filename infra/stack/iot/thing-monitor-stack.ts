import * as cdk from 'aws-cdk-lib';
import * as iot from 'aws-cdk-lib/aws-iot';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions'

import * as base from '../../../lib/template/stack/base/base-stack';
import { AppContext } from '../../../lib/template/app-context';

export class ThingMonitorStack extends base.BaseStack {

    constructor(appContext: AppContext, stackConfig: any) {
        super(appContext, stackConfig);

        const ruleList: any[] = [
            { name: 'thing_updated', topic: 'update/accepted', sns_topic: 'node_updated_topic_test', sql_fields: 'topic(3) as thing_name, topic(6) as shadow_name, state.reported as reported' },
            { name: 'thing_deleted', topic: 'delete/accepted', sns_topic: 'node_deleted_topic_test', sql_fields: 'topic(3) as thing_name, topic(6) as shadow_name' },
        ];

        ruleList.forEach((rule) => { this.createIotRule(rule.name, rule.topic, rule.sns_topic, rule.sql_fields) });
    }

    // We need to add a new rule to here to cover the update document rules
    /*

SQL statement
SELECT topic(3) as thing_name, topic(6) as shadow_name, previous as previous, current as current FROM '$aws/things/+/shadow/name/+/update/documents'

SNS topic: node_updated_topic
HTTPS: https://matterdashboard.netlify.app/.netlify/functions/shadowUpdateWebhook

    */

    // https://docs.aws.amazon.com/iot/latest/developerguide/registry-events.html
    private createIotRule(ruleName: string, topic: string, sns_topic: string, sql_fields: string) {
        const sql = `SELECT ${sql_fields} FROM '$aws/things/+/shadow/name/+/${topic}'`;

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
            handler: `handler.lambda_handler_${ruleName}`,
            timeout: cdk.Duration.seconds(120),
            runtime: lambda.Runtime.PYTHON_3_10,
            environment: {
                DATABASE: this.stackConfig.Database,
                HOST: this.stackConfig.Host,
                PASSWORD: this.stackConfig.Password,
                USERNAME: this.stackConfig.Username,
            },
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

