// Minimal C ABI for Qt/Python. Sparkle owns download, validation and replacement.
#import <Foundation/Foundation.h>
#import <Sparkle/Sparkle.h>

typedef int (*CanShutdownCallback)(void);
typedef void (*ShutdownCallback)(void);
typedef void (*EventCallback)(const char *);

static CanShutdownCallback canShutdown;
static ShutdownCallback requestShutdown;
static EventCallback notifyEvent;

@interface ICSTeXUpdaterDelegate : NSObject <SPUUpdaterDelegate>
@end

@implementation ICSTeXUpdaterDelegate
- (NSString *)feedURLStringForUpdater:(SPUUpdater *)updater {
    // Never let legacy Sparkle preferences redirect the build-bound feed.
    return NSBundle.mainBundle.infoDictionary[@"SUFeedURL"];
}
- (BOOL)updaterShouldPromptForPermissionToCheckForUpdates:(SPUUpdater *)updater {
    return NO;
}
- (NSArray<NSString *> *)allowedSystemProfileKeysForUpdater:(SPUUpdater *)updater {
    return @[];
}
- (BOOL)updater:(SPUUpdater *)updater shouldDownloadReleaseNotesForUpdate:(SUAppcastItem *)item {
    return NO;
}
- (BOOL)updaterShouldRelaunchApplication:(SPUUpdater *)updater {
    // Sparkle 2.9.6 SPUInstallerDriver calls this before every install attempt
    // and aborts installation on NO (including attempts without relaunch).
    return canShutdown != NULL && canShutdown() != 0;
}
- (void)updaterWillRelaunchApplication:(SPUUpdater *)updater {
    if (requestShutdown != NULL) requestShutdown();
}
- (void)updater:(SPUUpdater *)updater didFindValidUpdate:(SUAppcastItem *)item {
    if (notifyEvent != NULL) notifyEvent("available");
}
- (void)updaterDidNotFindUpdate:(SPUUpdater *)updater error:(NSError *)error {
    if (notifyEvent != NULL) notifyEvent("no_update");
}
- (void)userDidCancelDownload:(SPUUpdater *)updater {
    if (notifyEvent != NULL) notifyEvent("cancelled");
}
- (void)updater:(SPUUpdater *)updater didAbortWithError:(NSError *)error {
    if (notifyEvent != NULL) notifyEvent("error");
}
- (void)updater:(SPUUpdater *)updater didFinishUpdateCycleForUpdateCheck:(SPUUpdateCheck)check error:(NSError *)error {
    if (notifyEvent != NULL) notifyEvent("finished");
}
@end

static SPUStandardUpdaterController *controller;
static ICSTeXUpdaterDelegate *delegate;

__attribute__((visibility("default")))
int icstex_update_init(const char *feed, const char *key, const char *sequence,
                      CanShutdownCallback canQuit, ShutdownCallback quit,
                      EventCallback event) {
    if (![NSThread isMainThread] || controller != nil || !feed || !key || !sequence || !canQuit || !quit) return 0;
    NSDictionary *info = NSBundle.mainBundle.infoDictionary;
    if (![info[@"SUFeedURL"] isEqualToString:@(feed)] ||
        ![info[@"SUPublicEDKey"] isEqualToString:@(key)] ||
        ![info[@"CFBundleVersion"] isEqualToString:@(sequence)] ||
        ![info[@"SUVerifyUpdateBeforeExtraction"] boolValue] ||
        ![info[@"SURequireSignedFeed"] boolValue] ||
        [info[@"SUSignedFeedFailureExpirationInterval"] integerValue] != 0 ||
        [info[@"SUAllowsAutomaticUpdates"] boolValue]) return 0;
    canShutdown = canQuit;
    requestShutdown = quit;
    notifyEvent = event;
    delegate = [ICSTeXUpdaterDelegate new];
    controller = [[SPUStandardUpdaterController alloc] initWithStartingUpdater:NO
                                                            updaterDelegate:delegate
                                                         userDriverDelegate:nil];
    // Enforce policy even if older native preferences exist. Qt schedules checks.
    controller.updater.automaticallyChecksForUpdates = NO;
    controller.updater.automaticallyDownloadsUpdates = NO;
    controller.updater.sendsSystemProfile = NO;
    NSError *error = nil;
    if (![controller.updater startUpdater:&error]) {
        controller = nil;
        delegate = nil;
        canShutdown = NULL;
        requestShutdown = NULL;
        notifyEvent = NULL;
        return 0;
    }
    return 1;
}

__attribute__((visibility("default")))
int icstex_update_check(int userInitiated) {
    if (![NSThread isMainThread] || controller == nil || !controller.updater.canCheckForUpdates) return 0;
    if (userInitiated) [controller checkForUpdates:nil];
    else [controller.updater checkForUpdatesInBackground];
    return 1;
}

__attribute__((visibility("default")))
void icstex_update_cleanup(void) {
    if (![NSThread isMainThread]) return;
    canShutdown = NULL;
    requestShutdown = NULL;
    notifyEvent = NULL;
    controller.updater.automaticallyChecksForUpdates = NO;
    // Keep objects alive until process exit: an in-flight XPC callback may still
    // hold the updater. Null C callbacks make late notifications harmless.
}
