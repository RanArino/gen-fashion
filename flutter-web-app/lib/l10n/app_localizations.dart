import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_ja.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('ja')
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'gen-fashion'**
  String get appTitle;

  /// No description provided for @navCloset.
  ///
  /// In en, this message translates to:
  /// **'Closet'**
  String get navCloset;

  /// No description provided for @navCoordinate.
  ///
  /// In en, this message translates to:
  /// **'Coordinate'**
  String get navCoordinate;

  /// No description provided for @navHistory.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get navHistory;

  /// No description provided for @navShared.
  ///
  /// In en, this message translates to:
  /// **'Shared'**
  String get navShared;

  /// No description provided for @appHelpTooltip.
  ///
  /// In en, this message translates to:
  /// **'How this app works'**
  String get appHelpTooltip;

  /// No description provided for @appHelpTitle.
  ///
  /// In en, this message translates to:
  /// **'How this app works'**
  String get appHelpTitle;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @languageJapanese.
  ///
  /// In en, this message translates to:
  /// **'Japanese'**
  String get languageJapanese;

  /// No description provided for @languageEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get languageEnglish;

  /// No description provided for @loginEyebrow.
  ///
  /// In en, this message translates to:
  /// **'Personal styling studio'**
  String get loginEyebrow;

  /// No description provided for @loginSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in to manage your closet.'**
  String get loginSubtitle;

  /// No description provided for @signInLocal.
  ///
  /// In en, this message translates to:
  /// **'Sign in locally'**
  String get signInLocal;

  /// No description provided for @signInGoogle.
  ///
  /// In en, this message translates to:
  /// **'Sign in with Google'**
  String get signInGoogle;

  /// No description provided for @signingIn.
  ///
  /// In en, this message translates to:
  /// **'Signing in...'**
  String get signingIn;

  /// No description provided for @signInFailed.
  ///
  /// In en, this message translates to:
  /// **'Sign-in failed: {error}'**
  String signInFailed(Object error);

  /// No description provided for @closetTitle.
  ///
  /// In en, this message translates to:
  /// **'Closet'**
  String get closetTitle;

  /// No description provided for @closetHelpPurpose.
  ///
  /// In en, this message translates to:
  /// **'Your Closet stores photos of clothes you own or are considering, up to 20 items. Coordinate uses these items to build outfits.'**
  String get closetHelpPurpose;

  /// No description provided for @closetHelpUpload.
  ///
  /// In en, this message translates to:
  /// **'Tap \"Add item\" to upload a photo. The app analyzes it in the background and fills in category, color, season, and tags automatically; edit them anytime from the pencil icon.'**
  String get closetHelpUpload;

  /// No description provided for @closetHelpFilters.
  ///
  /// In en, this message translates to:
  /// **'Use the filters above to narrow the grid: \"Owned\" vs \"Interesting\" shows items you already have versus saved suggestions, and the category chips narrow further within the selected ownership filter.'**
  String get closetHelpFilters;

  /// No description provided for @emptyClosetHelpHint.
  ///
  /// In en, this message translates to:
  /// **'New here? Tap the ⓘ icon above for help.'**
  String get emptyClosetHelpHint;

  /// No description provided for @addItem.
  ///
  /// In en, this message translates to:
  /// **'Add item'**
  String get addItem;

  /// No description provided for @uploading.
  ///
  /// In en, this message translates to:
  /// **'Uploading...'**
  String get uploading;

  /// No description provided for @uploadQueued.
  ///
  /// In en, this message translates to:
  /// **'Upload queued; analyzing...'**
  String get uploadQueued;

  /// No description provided for @closetFull.
  ///
  /// In en, this message translates to:
  /// **'Closet is full (20 items).'**
  String get closetFull;

  /// No description provided for @uploadFailed.
  ///
  /// In en, this message translates to:
  /// **'Upload failed: {error}'**
  String uploadFailed(Object error);

  /// No description provided for @deleteItemQuestion.
  ///
  /// In en, this message translates to:
  /// **'Delete item?'**
  String get deleteItemQuestion;

  /// No description provided for @deleteItemBody.
  ///
  /// In en, this message translates to:
  /// **'This removes the item from your closet.'**
  String get deleteItemBody;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @deleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete failed: {error}'**
  String deleteFailed(Object error);

  /// No description provided for @editMetadata.
  ///
  /// In en, this message translates to:
  /// **'Edit item metadata'**
  String get editMetadata;

  /// No description provided for @category.
  ///
  /// In en, this message translates to:
  /// **'Category'**
  String get category;

  /// No description provided for @colorsComma.
  ///
  /// In en, this message translates to:
  /// **'Colors (comma separated)'**
  String get colorsComma;

  /// No description provided for @season.
  ///
  /// In en, this message translates to:
  /// **'Season'**
  String get season;

  /// No description provided for @tagsComma.
  ///
  /// In en, this message translates to:
  /// **'Tags (comma separated)'**
  String get tagsComma;

  /// No description provided for @gender.
  ///
  /// In en, this message translates to:
  /// **'Gender'**
  String get gender;

  /// No description provided for @genderCommon.
  ///
  /// In en, this message translates to:
  /// **'Common'**
  String get genderCommon;

  /// No description provided for @genderFemale.
  ///
  /// In en, this message translates to:
  /// **'Female'**
  String get genderFemale;

  /// No description provided for @genderMale.
  ///
  /// In en, this message translates to:
  /// **'Male'**
  String get genderMale;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @updateFailed.
  ///
  /// In en, this message translates to:
  /// **'Update failed: {error}'**
  String updateFailed(Object error);

  /// No description provided for @emptyCloset.
  ///
  /// In en, this message translates to:
  /// **'Add your first item to get started.'**
  String get emptyCloset;

  /// No description provided for @unknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown'**
  String get unknown;

  /// No description provided for @analyzing.
  ///
  /// In en, this message translates to:
  /// **'Analyzing...'**
  String get analyzing;

  /// No description provided for @analysisFailed.
  ///
  /// In en, this message translates to:
  /// **'Analysis failed'**
  String get analysisFailed;

  /// No description provided for @statusProcessing.
  ///
  /// In en, this message translates to:
  /// **'PROCESSING'**
  String get statusProcessing;

  /// No description provided for @statusReady.
  ///
  /// In en, this message translates to:
  /// **'READY'**
  String get statusReady;

  /// No description provided for @statusError.
  ///
  /// In en, this message translates to:
  /// **'ERROR'**
  String get statusError;

  /// No description provided for @statusUnknown.
  ///
  /// In en, this message translates to:
  /// **'UNKNOWN'**
  String get statusUnknown;

  /// No description provided for @deleteTooltip.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get deleteTooltip;

  /// No description provided for @editMetadataTooltip.
  ///
  /// In en, this message translates to:
  /// **'Edit metadata'**
  String get editMetadataTooltip;

  /// No description provided for @coordinationTitle.
  ///
  /// In en, this message translates to:
  /// **'Coordination'**
  String get coordinationTitle;

  /// No description provided for @helpCoordinateIntro.
  ///
  /// In en, this message translates to:
  /// **'Choose a styling mode and a clothing source, then generate a complete outfit.'**
  String get helpCoordinateIntro;

  /// No description provided for @modeStandard.
  ///
  /// In en, this message translates to:
  /// **'Closet Styling'**
  String get modeStandard;

  /// No description provided for @modeAssisted.
  ///
  /// In en, this message translates to:
  /// **'Style & Shop'**
  String get modeAssisted;

  /// No description provided for @modeStandardHint.
  ///
  /// In en, this message translates to:
  /// **'Creates a full outfit using only your closet items.'**
  String get modeStandardHint;

  /// No description provided for @modeAssistedHint.
  ///
  /// In en, this message translates to:
  /// **'Pick up to 3 of your own clothes; AI styles a full outfit and suggests items you can buy on Rakuten.'**
  String get modeAssistedHint;

  /// No description provided for @analyzingItem.
  ///
  /// In en, this message translates to:
  /// **'Analyzing...'**
  String get analyzingItem;

  /// No description provided for @anchorItemsLabel.
  ///
  /// In en, this message translates to:
  /// **'Your clothes (up to 3)'**
  String get anchorItemsLabel;

  /// No description provided for @anchorLimitReached.
  ///
  /// In en, this message translates to:
  /// **'You can select up to 3 items.'**
  String get anchorLimitReached;

  /// No description provided for @noReadyAnchorItems.
  ///
  /// In en, this message translates to:
  /// **'No ready closet items yet. Upload one to begin.'**
  String get noReadyAnchorItems;

  /// No description provided for @sourceRakuten.
  ///
  /// In en, this message translates to:
  /// **'Rakuten'**
  String get sourceRakuten;

  /// No description provided for @addToCloset.
  ///
  /// In en, this message translates to:
  /// **'Add to closet'**
  String get addToCloset;

  /// No description provided for @savedAsInteresting.
  ///
  /// In en, this message translates to:
  /// **'Saved as Interesting'**
  String get savedAsInteresting;

  /// No description provided for @importFailed.
  ///
  /// In en, this message translates to:
  /// **'Save failed: {error}'**
  String importFailed(Object error);

  /// No description provided for @coordinateReadyNotification.
  ///
  /// In en, this message translates to:
  /// **'Your coordinate is ready.'**
  String get coordinateReadyNotification;

  /// No description provided for @coordinateFailedNotification.
  ///
  /// In en, this message translates to:
  /// **'Coordinate generation failed.'**
  String get coordinateFailedNotification;

  /// No description provided for @viewAction.
  ///
  /// In en, this message translates to:
  /// **'View'**
  String get viewAction;

  /// No description provided for @openProductPage.
  ///
  /// In en, this message translates to:
  /// **'Open product page'**
  String get openProductPage;

  /// No description provided for @saveInterestingDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Save Rakuten items to your closet?'**
  String get saveInterestingDialogTitle;

  /// No description provided for @saveInterestingDialogBody.
  ///
  /// In en, this message translates to:
  /// **'These Rakuten items were part of this outfit. Save the ones you like as \"Interesting\" so you can find them again.'**
  String get saveInterestingDialogBody;

  /// No description provided for @saveInterestingSkip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get saveInterestingSkip;

  /// No description provided for @saveInterestingConfirm.
  ///
  /// In en, this message translates to:
  /// **'Save selected'**
  String get saveInterestingConfirm;

  /// No description provided for @ownership.
  ///
  /// In en, this message translates to:
  /// **'Ownership'**
  String get ownership;

  /// No description provided for @ownershipOwned.
  ///
  /// In en, this message translates to:
  /// **'Owned'**
  String get ownershipOwned;

  /// No description provided for @ownershipInteresting.
  ///
  /// In en, this message translates to:
  /// **'Interesting'**
  String get ownershipInteresting;

  /// No description provided for @ownershipOwnedHint.
  ///
  /// In en, this message translates to:
  /// **'Items you already own.'**
  String get ownershipOwnedHint;

  /// No description provided for @ownershipInterestingHint.
  ///
  /// In en, this message translates to:
  /// **'Saved suggestions you haven\'t purchased yet.'**
  String get ownershipInterestingHint;

  /// No description provided for @filterAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get filterAll;

  /// No description provided for @noItemsMatchFilter.
  ///
  /// In en, this message translates to:
  /// **'No items match the selected filters.'**
  String get noItemsMatchFilter;

  /// No description provided for @sourceShared.
  ///
  /// In en, this message translates to:
  /// **'Shared'**
  String get sourceShared;

  /// No description provided for @sourceMine.
  ///
  /// In en, this message translates to:
  /// **'Mine'**
  String get sourceMine;

  /// No description provided for @sourceSharedHint.
  ///
  /// In en, this message translates to:
  /// **'Use demo items from our shared closet — no upload needed.'**
  String get sourceSharedHint;

  /// No description provided for @sourceMineHint.
  ///
  /// In en, this message translates to:
  /// **'Use items from your own closet.'**
  String get sourceMineHint;

  /// No description provided for @sharedCloset.
  ///
  /// In en, this message translates to:
  /// **'Shared closet'**
  String get sharedCloset;

  /// No description provided for @occasion.
  ///
  /// In en, this message translates to:
  /// **'Occasion'**
  String get occasion;

  /// No description provided for @style.
  ///
  /// In en, this message translates to:
  /// **'Style'**
  String get style;

  /// No description provided for @colors.
  ///
  /// In en, this message translates to:
  /// **'Colors'**
  String get colors;

  /// No description provided for @selectedGenerationLanguage.
  ///
  /// In en, this message translates to:
  /// **'Generation language: {language}'**
  String selectedGenerationLanguage(Object language);

  /// No description provided for @running.
  ///
  /// In en, this message translates to:
  /// **'Running'**
  String get running;

  /// No description provided for @start.
  ///
  /// In en, this message translates to:
  /// **'Start'**
  String get start;

  /// No description provided for @agentTrace.
  ///
  /// In en, this message translates to:
  /// **'Agent trace'**
  String get agentTrace;

  /// No description provided for @errorWithMessage.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String errorWithMessage(Object error);

  /// No description provided for @noSessionEvents.
  ///
  /// In en, this message translates to:
  /// **'No session events yet.'**
  String get noSessionEvents;

  /// No description provided for @chooseItems.
  ///
  /// In en, this message translates to:
  /// **'Choose items'**
  String get chooseItems;

  /// No description provided for @generateSelected.
  ///
  /// In en, this message translates to:
  /// **'Generate selected'**
  String get generateSelected;

  /// No description provided for @recommended.
  ///
  /// In en, this message translates to:
  /// **'Recommended'**
  String get recommended;

  /// No description provided for @item.
  ///
  /// In en, this message translates to:
  /// **'Item'**
  String get item;

  /// No description provided for @result.
  ///
  /// In en, this message translates to:
  /// **'Result'**
  String get result;

  /// No description provided for @coordinatePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Coordinate image will appear here.'**
  String get coordinatePlaceholder;

  /// No description provided for @traceSearchedCloset.
  ///
  /// In en, this message translates to:
  /// **'{agentName} searched closet - {count} candidates'**
  String traceSearchedCloset(Object agentName, Object count);

  /// No description provided for @traceSearchingCloset.
  ///
  /// In en, this message translates to:
  /// **'{agentName} is searching the closet'**
  String traceSearchingCloset(Object agentName);

  /// No description provided for @traceGeneratedCoordinate.
  ///
  /// In en, this message translates to:
  /// **'{agentName} generated the coordinate'**
  String traceGeneratedCoordinate(Object agentName);

  /// No description provided for @traceGeneratingCoordinate.
  ///
  /// In en, this message translates to:
  /// **'{agentName} is generating the coordinate'**
  String traceGeneratingCoordinate(Object agentName);

  /// No description provided for @tracePreview.
  ///
  /// In en, this message translates to:
  /// **'Preview'**
  String get tracePreview;

  /// No description provided for @traceRaw.
  ///
  /// In en, this message translates to:
  /// **'Raw'**
  String get traceRaw;

  /// No description provided for @traceDescription.
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get traceDescription;

  /// No description provided for @traceStyleDirection.
  ///
  /// In en, this message translates to:
  /// **'Style'**
  String get traceStyleDirection;

  /// No description provided for @traceWearer.
  ///
  /// In en, this message translates to:
  /// **'Wearer'**
  String get traceWearer;

  /// No description provided for @traceItemCount.
  ///
  /// In en, this message translates to:
  /// **'Items'**
  String get traceItemCount;

  /// No description provided for @traceModelUsed.
  ///
  /// In en, this message translates to:
  /// **'Model'**
  String get traceModelUsed;

  /// No description provided for @traceGenerationPrompt.
  ///
  /// In en, this message translates to:
  /// **'Prompt'**
  String get traceGenerationPrompt;

  /// No description provided for @traceTags.
  ///
  /// In en, this message translates to:
  /// **'Tags'**
  String get traceTags;

  /// No description provided for @traceTargetAgent.
  ///
  /// In en, this message translates to:
  /// **'Agent'**
  String get traceTargetAgent;

  /// No description provided for @traceItemsFound.
  ///
  /// In en, this message translates to:
  /// **'{count} items found'**
  String traceItemsFound(int count);

  /// No description provided for @traceQuery.
  ///
  /// In en, this message translates to:
  /// **'Query'**
  String get traceQuery;

  /// No description provided for @traceShopName.
  ///
  /// In en, this message translates to:
  /// **'Shop'**
  String get traceShopName;

  /// No description provided for @traceSearchingRakuten.
  ///
  /// In en, this message translates to:
  /// **'{agentName} is searching Rakuten'**
  String traceSearchingRakuten(Object agentName);

  /// No description provided for @traceSearchedRakuten.
  ///
  /// In en, this message translates to:
  /// **'{agentName} searched Rakuten - {count} candidates'**
  String traceSearchedRakuten(Object agentName, Object count);

  /// No description provided for @historyLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load history: {error}'**
  String historyLoadFailed(Object error);

  /// No description provided for @historyEmpty.
  ///
  /// In en, this message translates to:
  /// **'No completed coordinates yet.'**
  String get historyEmpty;

  /// No description provided for @helpHistoryBody.
  ///
  /// In en, this message translates to:
  /// **'History lists the outfits you\'ve already generated, newest first.'**
  String get helpHistoryBody;

  /// No description provided for @dateUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Date unavailable'**
  String get dateUnavailable;

  /// No description provided for @myCloset.
  ///
  /// In en, this message translates to:
  /// **'My Closet'**
  String get myCloset;

  /// No description provided for @sharedGalleryError.
  ///
  /// In en, this message translates to:
  /// **'Error: {error}'**
  String sharedGalleryError(Object error);

  /// No description provided for @sharedAttribution.
  ///
  /// In en, this message translates to:
  /// **'Shared closet images use the Clothing Dataset (CC BY-SA 4.0)'**
  String get sharedAttribution;

  /// No description provided for @sharedAboutBody.
  ///
  /// In en, this message translates to:
  /// **'The Shared closet contains sample clothing photos so you can try a full styling demo right away, without uploading any of your own items first.'**
  String get sharedAboutBody;

  /// No description provided for @sharedAboutDataset.
  ///
  /// In en, this message translates to:
  /// **'Image material: Clothing Dataset (CC BY-SA 4.0)'**
  String get sharedAboutDataset;

  /// No description provided for @sharedAboutAuthor.
  ///
  /// In en, this message translates to:
  /// **'Author: Alexey Grigorev'**
  String get sharedAboutAuthor;

  /// No description provided for @viewDataset.
  ///
  /// In en, this message translates to:
  /// **'View dataset on Kaggle'**
  String get viewDataset;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'ja'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'ja':
      return AppLocalizationsJa();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
