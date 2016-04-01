# --------------------------------------------------------------------
# Directory syncer by Alexander Sirotin (c) 2016
# Originally created for syncing between home NAS backup and Amazon cloud
# Both are mounted on the host machine (Amazon cloud is mounted using acd_cli)
# This program comes without any warranty, use it at your own risk.
# Feel free to contact me at sirotin@gmail.com
# --------------------------------------------------------------------

import os
import sys
import filecmp
import logging
import argparse
import shutil

class DirectorySyncer:
	# Note: Recursive function, goes over all the sub-directories as well
	def __compareTwoDirectories(self, left, right):
		logging.debug("Comparing between '%s' and '%s'" % (left, right))

		# Make sure both directories exists
		if not os.path.exists(left) or not os.path.isdir(left):
			raise Exception, "Provided left directory '%s' does not exist or not a directory!" % left
		
		if not os.path.exists(right) or not os.path.isdir(right):
			raise Exception, "Provided right directory '%s' does not exist or not a directory!" % right

		# Compare the two directories and create two lists containing the missing parts
		result = filecmp.dircmp(left, right)
		leftOnly = self.__removeSpecial(result.left_only)
		rightOnly = self.__removeSpecial(result.right_only)

		# Add full path to the elements
		leftOnly = self.__convertToFullPath(left, leftOnly)
		rightOnly = self.__convertToFullPath(right, rightOnly)

		# Get common dirs for recursive call
		dirs = self.__removeSpecial(result.common_dirs)
		for dir in dirs:
			childLeftOnly, childRightOnly = self.__compareTwoDirectories(os.path.join(left, dir), os.path.join(right, dir))
			leftOnly.extend(childLeftOnly)
			rightOnly.extend(childRightOnly)
		
		return leftOnly, rightOnly

	def __removeSpecial(self, list):
		return [x for x in list if not x.startswith(".")]

	def __convertToFullPath(self, basePath, list):
		for i in range(len(list)):
			list[i] = os.path.join(basePath, list[i])
		return list

	def __removeRootLocation(self, path, list):
		n = len(path) + 1
		for i in range(len(list)):
			list[i] = list[i][n:]
		return list

	def __calculateDiskSpace(self, list):
		diskSpace = 0
		for x in list:
			diskSpace += os.path.getsize(x)
			if os.path.isdir(x):
				content = [os.path.join(x, f) for f in os.listdir(x)]
				diskSpace += self.__calculateDiskSpace(content)
		return diskSpace

	def __askYesNoQuestion(self, message):
		yes = set(["yes", "y", ""])
		no = set(["no", "n"])

		while True:
			print("%s [Y/N] " % message)
			choice = raw_input().lower()
			if choice in yes:
				return True
			elif choice in no:
				return False
			else:
				print("Please response with a valid answer.")

	def __verboseSelectFromList(self, fromPath, toPath, list):
		return [x for x in list if self.__askYesNoQuestion("Copy from '%s' to '%s' ?" % (os.path.join(fromPath, x), os.path.join(toPath, x)))]

	def __copyMissingFiles(self, fromPath, toPath, list):
		for file in list:
			src = os.path.join(fromPath, file)
			dst = os.path.join(toPath, file)

			logging.debug("Copying '%s' to '%s'" % (src, dst))
			try:
				if os.path.isdir(src):
					shutil.copytree(src, dst)
				else:
					shutil.copy(src, dst)
			except Exception as e:
				# In case of exception, we want to remove dst in order to avoid partially copied files
				shutil.rmtree(dst)
				raise e

	def __showNeededDiskSpace(self, pointA, pointB, leftOnly, rightOnly):
		MB = 1024 * 1024.0
		logging.info("Needed disk space for sync point '%s' is %.2f MB" % (pointA, self.__calculateDiskSpace(rightOnly) / MB))
		logging.info("Needed disk space for sync point '%s' is %.2f MB" % (pointB, self.__calculateDiskSpace(leftOnly)) / MB)

	def sync(self, pointA, pointB, dryRun=False, verbose=False):
		print(self.__calculateDiskSpace(["/media/mybook/Photos/TODO"]))
		return

		if dryRun:
			logging.info("Syncing between '%s' and '%s' (Output only)" % (pointA, pointB))
		else:
			logging.info("Syncing between '%s' and '%s'" % (pointA, pointB))

		try:
			# Create two lists contains the differences between the given points
			leftOnly, rightOnly = self.__compareTwoDirectories(pointA, pointB)
			leftOnlyLen = len(leftOnly)
			rightOnlyLen = len(rightOnly)
			logging.info("Found %d differences (%d are missing in '%s' and %d are missing in '%s')" % (leftOnlyLen + rightOnlyLen, rightOnlyLen, pointA, leftOnlyLen, pointB))

			# In case of dryRun, Show the differences and quit
			if dryRun:
				for path in leftOnly:
					logging.info("Left only: %s" % path)
				for path in rightOnly:
					logging.info("Right only: %s" % path)

				# Show needed disk space
				self.__showNeededDiskSpace(pointA, pointB, leftOnly, rightOnly)

				return True

			# In case of verbose flag, ask the user what to do
			if verbose:
				leftOnly = self.__verboseSelectFromList(pointA, pointB, leftOnly)
				rightOnly = self.__verboseSelectFromList(pointB, pointA, rightOnly)

			# Show needed disk space
			self.__showNeededDiskSpace(pointA, pointB, leftOnly, rightOnly)

			# Remove base path from results
			leftOnly = self.__removeRootLocation(pointA, leftOnly)
			rightOnly = self.__removeRootLocation(pointB, rightOnly)

			# In case of verbose flag, recalculate number of differences
			if verbose:
				leftOnlyLen = len(leftOnly)
				rightOnlyLen = len(rightOnly)
			
			logging.info("Start processing %d differences (%d are missing in '%s' and %d are missing in '%s')" % (leftOnlyLen + rightOnlyLen, rightOnlyLen, pointA, leftOnlyLen, pointB))
			self.__copyMissingFiles(pointA, pointB, leftOnly)
			self.__copyMissingFiles(pointB, pointA, rightOnly)

		except Exception as e:
			logging.error(e.args[0])
			return False
		
		return True

def configure():
	# Configure the logger
	logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", datefmt="%d/%m/%Y %H:%M:%S", level=logging.DEBUG)

	# Read the command line arguments
	parser = argparse.ArgumentParser()
	parser.add_argument("-l", "--left", required=True)
	parser.add_argument("-r", "--right", required=True)
	parser.add_argument("-d", "--dry_run", action="store_const", const=True, default=False);
	parser.add_argument("-v", "--verbose", action="store_const", const=True, default=False);
	args = parser.parse_args()

	# Return the arguments
	return args

def main():
	args = configure()
	
	pointA = os.path.normpath(args.left)
	pointB = os.path.normpath(args.right)

	syncer = DirectorySyncer()
	syncer.sync(pointA, pointB, dryRun=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
	main()
