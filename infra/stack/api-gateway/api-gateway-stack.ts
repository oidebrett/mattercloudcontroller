import * as cdk from 'aws-cdk-lib';
import * as api from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as base from '../../../lib/template/stack/base/base-stack';
import { AppContext } from '../../../lib/template/app-context';
import { Construct } from 'constructs';

import * as deepmerge from 'deepmerge';
import { IRole } from 'aws-cdk-lib/aws-iam';

export class ApiGatewayDeploymentStack extends base.BaseStack {
    
  constructor(appContext: AppContext, stackConfig: any) {
      super(appContext, stackConfig);

      new ApiGatewayToIot(this, 'ApiGatewayToIotPattern', {
        iotEndpoint: stackConfig.IotEndpointAddress,
        apiGatewayCreateApiKey: true
      });
  }
}

/**
 * The properties for the ApiGatewayIot class.
 */
 export interface ApiGatewayToIotProps {
  /**
   * The AWS IoT endpoint subdomain to integrate the API Gateway with (e.g ab123cdefghij4l-ats). Added as AWS Subdomain to the Integration Request.
   *
   * @default - None.
   */
  readonly iotEndpoint: string,
  /**
   * Creates an api key and associates to usage plan if set to true
   *
   * @default - false
   */
  readonly apiGatewayCreateApiKey?: boolean,
  /**
   * The IAM role that is used by API Gateway to publish messages to IoT topics and Thing shadows.
   *
   * @default - An IAM role with iot:Publish access to all topics (topic/*) and iot:UpdateThingShadow access to all things (thing/*) is created.
   */
  readonly apiGatewayExecutionRole?: iam.IRole,
  /**
   * Optional user-provided props to override the default props for the API.
   *
   * @default - Default props are used.
   */
  readonly apiGatewayProps?: api.RestApiProps,
  /**
   * User provided props to override the default props for the CloudWatchLogs LogGroup.
   *
   * @default - Default props are used
   */
  readonly logGroupProps?: logs.LogGroupProps
}

/**
 * @summary The ApiGatewayIot class.
 */
export class ApiGatewayToIot extends Construct {
  public readonly apiGateway: api.RestApi;
  public readonly apiGatewayCloudWatchRole?: iam.Role;
  public readonly apiGatewayLogGroup: logs.LogGroup;
  public readonly apiGatewayRole: iam.IRole;
  private readonly iotEndpoint: string;
  private readonly requestValidator: api.IRequestValidator;
  private readonly getRequestValidator: api.IRequestValidator;
  // IoT Core topic nesting. A topic in a publish or subscribe request can have no more than 7 forward slashes (/).
  // This excludes the first 3 slashes in the mandatory segments for Basic Ingest
  // Refer IoT Limits - https://docs.aws.amazon.com/general/latest/gr/iot-core.html#limits_iot
  private readonly topicNestingLevel = 7;

  /**
   * @summary Constructs a new instance of the ApiGatewayIot class.
   * @param {cdk.App} scope - represents the scope for all the resources.
   * @param {string} id - this is a a scope-unique id.
   * @param {ApiGatewayToIotProps} props - user provided props for the construct
   * @since 0.8.0
   * @access public
   */
  constructor(scope: Construct, id: string, props: ApiGatewayToIotProps) {
    super(scope, id);

    // Assignment to local member variables to make these available to all member methods of the class.
    // (Split the string just in case user supplies fully qualified endpoint eg. ab123cdefghij4l-ats.iot.ap-south-1.amazonaws.com)
    this.iotEndpoint = props.iotEndpoint.trim().split('.')[0];

    // Mandatory params check
    if (!this.iotEndpoint || this.iotEndpoint.length < 0) {
      throw new Error('specify a valid iotEndpoint');
    }

    // Add additional params to the apiGatewayProps
    let extraApiGwProps = {
      binaryMediaTypes: ['application/octet-stream'],
      defaultMethodOptions: {
        apiKeyRequired: props.apiGatewayCreateApiKey
      }
    };


    // If apiGatewayProps are specified override the extra Api Gateway properties
    extraApiGwProps = consolidateProps(extraApiGwProps, props.apiGatewayProps);

    // Check whether an API Gateway execution role is specified?
    if (props.apiGatewayExecutionRole) {
      this.apiGatewayRole = props.apiGatewayExecutionRole;
    } else {
      // JSON that will be used for policy document
      const policyJSON = {
        Version: "2012-10-17",
        Statement: [
          {
            Action: [
              "iot:UpdateThingShadow",
              "iot:GetThingShadow",
              "iot:ListNamedShadowsForThing"
            ],
            Resource: `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:thing/*`,
            Effect: "Allow"
          },
          {
            Action: [
              "iot:Publish"
            ],
            Resource: `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/*`,
            Effect: "Allow"
          }
        ]
      };

      // Create a policy document
      const policyDocument: iam.PolicyDocument = iam.PolicyDocument.fromJson(policyJSON);

      // Props for IAM Role
      const iamRoleProps: iam.RoleProps = {
        assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
        path: '/',
        inlinePolicies: { awsapigatewayiotpolicy: policyDocument }
      };

      // Create a policy that overrides the default policy that gets created with the construct
      this.apiGatewayRole = new iam.Role(this, 'apigateway-iot-role', iamRoleProps);
    }

    // Setup the API Gateway
    this.apiGateway = GlobalRestApi(this, extraApiGwProps, props.logGroupProps);

    // Validate the Query Params
    const requestValidatorProps: api.RequestValidatorProps = {
      restApi: this.apiGateway,
      validateRequestBody: false,
      validateRequestParameters: true
    };
    this.requestValidator = new api.RequestValidator(this, `aws-apigateway-iot-req-val`, requestValidatorProps);

    // Validate the GET Params
    const getRequestValidatorProps: api.RequestValidatorProps = {
      restApi: this.apiGateway,
      validateRequestBody: false,
      validateRequestParameters: false
    };
    this.getRequestValidator = new api.RequestValidator(this, `aws-apigateway-iot-getreq-val`, getRequestValidatorProps);

    // Create a resource for messages '/message'
    const msgResource: api.IResource = this.apiGateway.root.addResource('message');

    // Create resources from '/message/{topic-level-1}' through '/message/{topic-level-1}/..../{topic-level-7}'
    let topicPath = 'topics';
    let parentNode = msgResource;
    let integParams = {};
    let methodParams = {};
    for (let pathLevel = 1; pathLevel <= this.topicNestingLevel; pathLevel++) {
      const topicName = `topic-level-${pathLevel}`;
      const topicResource: api.IResource = parentNode.addResource(`{${topicName}}`);
      const integReqParam = JSON.parse(`{"integration.request.path.${topicName}": "method.request.path.${topicName}"}`);
      const methodReqParam = JSON.parse(`{"method.request.path.${topicName}": true}`);
      topicPath = `${topicPath}/{${topicName}}`;
      integParams = Object.assign(integParams, integReqParam);
      methodParams = Object.assign(methodParams, methodReqParam);
      this.addResourceMethod(topicResource, props, topicPath, integParams, methodParams, 'POST');
      parentNode = topicResource;
    }

    // Create a resource for shadow updates '/shadow'
    const shadowResource: api.IResource = this.apiGateway.root.addResource('shadow');

    // Create resource '/shadow/{thingName}'0
    const defaultShadowResource: api.IResource = shadowResource.addResource('{thingName}');
    const shadowReqParams = {'integration.request.path.thingName': 'method.request.path.thingName'};
    const methodShadowReqParams = {'method.request.path.thingName': true};
    this.addResourceMethod(defaultShadowResource, props, 'things/{thingName}/shadow',
      shadowReqParams, methodShadowReqParams, 'POST');

    // Create resource '/shadow/{thingName}/{shadowName}'
    const namedShadowResource: api.IResource = defaultShadowResource.addResource('{shadowName}');
    const namedShadowReqParams = Object.assign({
      'integration.request.path.shadowName': 'method.request.path.shadowName'},
    shadowReqParams);
    const methodNamedShadowReqParams = Object.assign({
      'method.request.path.shadowName': true}, methodShadowReqParams);
    this.addResourceMethod(namedShadowResource, props, 'things/{thingName}/shadow?name={shadowName}',
      namedShadowReqParams, methodNamedShadowReqParams, 'POST');

    // Create a resource for getting things '/things'
    // e.g HTTP GET https://endpoint/things/thingName/shadow?name=shadowName
    //Add a GET request on same resource '/shadow/{thingName}/{shadowName}'
    this.addResourceMethod(namedShadowResource, props, 'things/{thingName}/shadow?name={shadowName}',
    namedShadowReqParams, methodNamedShadowReqParams, 'GET');

    // Create a resource for getting a list of shadowns '/things'
    // e.g HTTP GET /api/things/shadow/ListNamedShadowsForThing/thingName?nextToken=nextToken&pageSize=pageSize HTTP/1.1
    // Create a resource for shadow updates '/api'
    const apiResource: api.IResource = this.apiGateway.root.addResource('api');
    // Create resource '/api/things'
    const apiThingsResource: api.IResource = apiResource.addResource('things');
    // Create resource '/api//things/shadow'
    const apiThingsShadowResource: api.IResource = apiThingsResource.addResource('shadow');
    // Create resource '/api/things/shadow/ListNamedShadowsForThing/{thingName}'
    const apiThingsShadowListResource: api.IResource = apiThingsShadowResource.addResource('ListNamedShadowsForThing');
    const listNamedShadowResource: api.IResource = apiThingsShadowListResource.addResource('{thingName}');
    this.addResourceMethod(listNamedShadowResource, props, 'api/things/shadow/ListNamedShadowsForThing/{thingName}', namedShadowReqParams, methodNamedShadowReqParams, 'GET');


  }

  /**
   * Adds a method to specified resource
   * @param resource API Gateway resource to which this method is added
   * @param resourcePath path of resource from root
   * @param integReqParams request paramters for the Integration method
   * @param methodReqParams request parameters at Method level
   */
   private addResourceMethod(resource: api.IResource, props: ApiGatewayToIotProps, resourcePath: string,
    integReqParams: { [key: string]: string },
    methodReqParams: { [key: string]: boolean },
    httpApiMethod: string) {
    const integResp: api.IntegrationResponse[] = [
      {
        statusCode: "200",
        selectionPattern: "2\\d{2}",
        responseTemplates: {
          "application/json": "$input.json('$')"
        }
      },
      {
        statusCode: "500",
        selectionPattern: "5\\d{2}",
        responseTemplates: {
          "application/json": "$input.json('$')"
        }
      },
      {
        statusCode: "403",
        responseTemplates: {
          "application/json": "$input.json('$')"
        }
      }
    ];

    // Method responses for the resource
    const methodResp: api.MethodResponse[] = [
      {
        statusCode: "200"
      },
      {
        statusCode: "500"
      },
      {
        statusCode: "403"
      }
    ];

    // Override the default Integration Request Props
    const integrationReqProps = {
      subdomain: this.iotEndpoint,
      options: {
        requestParameters: integReqParams,
        integrationResponses: integResp,
        passthroughBehavior: api.PassthroughBehavior.WHEN_NO_MATCH
      }
    };

    // Override the default Method Options
    const resourceMethodOptions = {
      requestParameters: methodReqParams,
      methodResponses: methodResp,
    };

    //Check validation depending on whether GET or POST
    let requestTemplate = "$input.json('$')";
    let requestValidator = this.requestValidator
    let contentType = "";
    if (httpApiMethod == 'GET'){
      requestTemplate = "";
      requestValidator = this.getRequestValidator
      contentType = "'text/html'"
    }

    const resourceMethodParams: AddProxyMethodToApiResourceInputParams = {
      service: 'iotdata',
      path: resourcePath,
      apiGatewayRole: this.apiGatewayRole,
      apiMethod: httpApiMethod,
      apiResource: resource,
      requestTemplate: requestTemplate,
      requestValidator: requestValidator,
      contentType: contentType,
      awsIntegrationProps: integrationReqProps,
      methodOptions: resourceMethodOptions
    };

    const apiMethod = addProxyMethodToApiResource(
      resourceMethodParams
    );

    if (props.apiGatewayCreateApiKey === true) {
      // cfn Nag doesn't like having a HTTP Method with Authorization Set to None, supress the warning
      addCfnSuppressRules(apiMethod, [
        {
          id: "W59",
          reason:
            "When ApiKey is being created, we also set apikeyRequired to true, so techincally apiGateway still looks for apiKey even though user specified AuthorizationType to NONE",
        },
      ]);
    }
  }
}

/**
 * Builds and returns a standard api.RestApi.
 * @param scope - the construct to which the RestApi should be attached to.
 * @param apiGatewayProps - (optional) user-specified properties to override the default properties.
 */
export function GlobalRestApi(scope: Construct, apiGatewayProps?: api.RestApiProps,
  logGroupProps?: logs.LogGroupProps): api.RestApi {
    const defaultProps = DefaultGlobalRestApiProps();
    const restApi = configureRestApi(scope, defaultProps, apiGatewayProps);
  return restApi;
}

/**
 * Creates and configures an api.RestApi.
 * @param scope - the construct to which the RestApi should be attached to.
 * @param defaultApiGatewayProps - the default properties for the RestApi.
 * @param apiGatewayProps - (optional) user-specified properties to override the default properties.
 */
 function configureRestApi(scope: Construct, defaultApiGatewayProps: api.RestApiProps, apiGatewayProps?: api.RestApiProps): api.RestApi {

  // API Gateway doesn't allow both endpointTypes and endpointConfiguration, check whether endPointTypes exists
  if (apiGatewayProps?.endpointTypes) {
    throw Error('Solutions Constructs internally uses endpointConfiguration, use endpointConfiguration instead of endpointTypes');
  }

  // Define the API
  let _api: api.RestApi;

  const _apiGatewayProps = consolidateProps(defaultApiGatewayProps, apiGatewayProps, { cloudWatchRole: false });
  //const _apiGatewayProps = apiGatewayProps;
  _api = new api.RestApi(scope, 'RestApi', _apiGatewayProps);


  // Configure Usage Plan
  const usagePlanProps: api.UsagePlanProps = {
    apiStages: [{
      api: _api,
      stage: _api.deploymentStage
    }]
  };

  const plan = _api.addUsagePlan('UsagePlan', usagePlanProps);

  // If requireApiKey param is set to true, create a api key & associate to Usage Plan
  if (apiGatewayProps?.defaultMethodOptions?.apiKeyRequired === true) {
    // Configure Usage Plan with API Key
    const key = _api.addApiKey('ApiKey');
    plan.addApiKey(key);
  }

  // Return the API and CW Role
  return _api;
}

/**
 * Creates the props to be used to instantiate a CDK L2 construct within a Solutions Construct
 *
 * @param defaultProps The default props to be used by the construct
 * @param clientProps Optional properties passed in from the client in the props object
 * @param constructProps Optional properties required by the construct for the construct to work (override any other values)
 * @returns The properties to use - all values prioritized:
 *  1) constructProps value
 *  2) clientProps value
 *  3) defaultProps value
 */
 export function consolidateProps(defaultProps: object, clientProps?: object, constructProps?: object): any {
  let result: object = defaultProps;

  if (clientProps) {
    result = overrideProps(result, clientProps);
  }

  if (constructProps) {
    result = overrideProps(result, constructProps);
  }

  return result;
}

export function overrideProps(DefaultProps: object, userProps: object, concatArray: boolean = false): any {
  // Override the sensible defaults with user provided props
  if (concatArray) {
    return deepmerge(DefaultProps, userProps, {
      arrayMerge: combineMerge,
      isMergeableObject: isPlainObject
    });
  } else {
    return deepmerge(DefaultProps, userProps, {
      arrayMerge: overwriteMerge,
      isMergeableObject: isPlainObject
    });
  }
}

function combineMerge(target: any[], source: any[]) {
  return target.concat(source);
}

function overwriteMerge(target: any[], source: any[]) {
  target = source;
  return target;
}

function isObject(val: object) {
  return val != null && typeof val === 'object'
        && Object.prototype.toString.call(val) === '[object Object]';
}

function isPlainObject(o: object) {
  if (Array.isArray(o) === true) {
    return true;
  }

  if (isObject(o) === false) {
    return false;
  }
 // If has modified constructor
 const ctor = o.constructor;
 if (typeof ctor !== 'function') {
   return false;
 }

 // If has modified prototype
 const prot = ctor.prototype;
 if (isObject(prot) === false) {
   return false;
 }

 // If constructor does not have an Object-specific method
 if (prot.hasOwnProperty('isPrototypeOf') === false) {
   return false;
 }

 // Most likely a plain Object
 return true;
}

export interface AddProxyMethodToApiResourceInputParams {
  readonly service: string,
  readonly action?: string,
  readonly path?: string,
  readonly apiResource: api.IResource,
  readonly apiMethod: string,
  readonly apiGatewayRole: IRole,
  readonly requestTemplate: string,
  readonly contentType?: string,
  readonly requestValidator?: api.IRequestValidator,
  readonly requestModel?: { [contentType: string]: api.IModel; },
  readonly awsIntegrationProps?: api.AwsIntegrationProps | any,
  readonly methodOptions?: api.MethodOptions
}

export function addProxyMethodToApiResource(params: AddProxyMethodToApiResourceInputParams): api.Method {

  let baseProps: api.AwsIntegrationProps = {
    service: params.service,
    integrationHttpMethod: params.apiMethod,
    options: {
      passthroughBehavior: api.PassthroughBehavior.NEVER,
      credentialsRole: params.apiGatewayRole,
      requestParameters: {
        "integration.request.header.Content-Type": params.contentType ? params.contentType : "'application/json'"
      },
      requestTemplates: {
        "application/json": params.requestTemplate
      },
      integrationResponses: [
        {
          statusCode: "200"
        },
        {
          statusCode: "500",
          responseTemplates: {
            "text/html": "Error"
          },
          selectionPattern: "500"
        }
      ]
    }
  };

  let extraProps;

  if (params.action) {
    extraProps = {
      action: params.action
    };
  } else if (params.path) {
    extraProps = {
      path: params.path
    };
  } else {
    throw Error('Either action or path is required');
  }

  // Setup the API Gateway AWS Integration
  baseProps = Object.assign(baseProps, extraProps);

  let apiGatewayIntegration;
  const newProps = consolidateProps(baseProps, params.awsIntegrationProps);

  apiGatewayIntegration = new api.AwsIntegration(newProps);

  const defaultMethodOptions = {
    methodResponses: [
      {
        statusCode: "200",
        responseParameters: {
          "method.response.header.Content-Type": true
        }
      },
      {
        statusCode: "500",
        responseParameters: {
          "method.response.header.Content-Type": true
        },
      }
    ],
    requestValidator: params.requestValidator,
    requestModels: params.requestModel
  };

  let apiMethod;

  // Setup the API Gateway method
  const overridenProps = consolidateProps(defaultMethodOptions, params.methodOptions);
  apiMethod = params.apiResource.addMethod(params.apiMethod, apiGatewayIntegration, overridenProps);

  return apiMethod;
}

/**
 * The CFN NAG suppress rule interface
 * @interface CfnNagSuppressRule
 */
 export interface CfnNagSuppressRule {
  readonly id: string;
  readonly reason: string;
}

/**
 * Adds CFN NAG suppress rules to the CDK resource.
 * @param resource The CDK resource
 * @param rules The CFN NAG suppress rules
 */
 export function addCfnSuppressRules(resource: cdk.Resource | cdk.CfnResource, rules: CfnNagSuppressRule[]) {
  if (resource instanceof cdk.Resource) {
    resource = resource.node.defaultChild as cdk.CfnResource;
  }

  if (resource.cfnOptions.metadata?.cfn_nag?.rules_to_suppress) {
    resource.cfnOptions.metadata?.cfn_nag.rules_to_suppress.push(...rules);
  } else {
    resource.addMetadata('cfn_nag', {
      rules_to_suppress: rules
    });
  }

  
}

/**
 * Provides the default set of properties for Edge/Global RestApi
 * @param _logGroup - CW Log group for Api Gateway access logging
 */
 export function DefaultGlobalRestApiProps() {
  return DefaultRestApiProps([api.EndpointType.EDGE]);
}
/**
 * Private function to configure an api.RestApiProps
 * @param scope - the construct to which the RestApi should be attached to.
 * @param _endpointType - endpoint type for Api Gateway e.g. Regional, Global, Private
 * @param _logGroup - CW Log group for Api Gateway access logging
 */
 function DefaultRestApiProps(_endpointType: api.EndpointType[]): api.RestApiProps {
  return {
    endpointConfiguration: {
      types: _endpointType
    },
    cloudWatchRole: false,
    // Configure API Gateway Access logging
    deployOptions: {
      loggingLevel: api.MethodLoggingLevel.INFO,
      dataTraceEnabled: false,
      tracingEnabled: true
    },
    defaultMethodOptions: {
      authorizationType: api.AuthorizationType.IAM
    }

  } as api.RestApiProps;
}