#!/usr/bin/env node
import { AppContext } from '../lib/template/app-context';
import { ThingInstallerStack } from './stack/iot/thing-installer-stack';
import { ComponentUploadStack } from './stack/greengrass/component-upload-stack';
import { ComponentDeploymentStack } from './stack/greengrass/component-deployment-stack';

const appContext = new AppContext({
    appConfigEnvName: 'APP_CONFIG',
});

if (appContext.stackCommonProps != undefined) {
    new ThingInstallerStack(appContext, appContext.appConfig.Stack.ThingInstaller);
    
    new ComponentUploadStack(appContext, appContext.appConfig.Stack.ComponentUpload);
    new ComponentDeploymentStack(appContext, appContext.appConfig.Stack.ComponentDeployment);
    
} else {
    console.error('[Error] wrong AppConfigFile');
}
